"""One authoritative SQLite store with durable pending operations and audit events."""
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
import hashlib
import hmac
import json
import re
from pathlib import Path
import secrets
import sqlite3
import uuid

from .catalog import identifier
from .barcodes import read_scan, aliases


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError("Quantity must be a positive whole number.")


def medicine(value):
    if not isinstance(value, dict):
        raise ValueError("Supply medication details as an object.")
    keys = ("generic_name", "ndc", "lot", "expiry_date", "unit", "description", "brand_name", "labeler_name")
    result = {key: str(value.get(key) or "").strip() for key in keys}
    for key in ("generic_name", "ndc", "lot", "expiry_date", "unit"):
        if not result[key]:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    result["ndc"] = identifier(result["ndc"])
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", result["expiry_date"]):
            raise ValueError("Expected YYYY-MM-DD")
        expiry = date.fromisoformat(result["expiry_date"])
    except ValueError as exc:
        raise ValueError("Enter the actual package expiration as YYYY-MM-DD.") from exc
    if expiry < date.today():
        raise ValueError("Expired stock cannot be loaded or dispensed.")
    return result


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class Store:
    def __init__(self, path):
        self.local_session = False
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS compartments (
                    id INTEGER PRIMARY KEY CHECK(id BETWEEN 1 AND 4),
                    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                    product TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, compartment INTEGER NOT NULL REFERENCES compartments(id),
                    kind TEXT NOT NULL, requested INTEGER NOT NULL, product TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL,
                    operator TEXT NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_operation ON operations((1))
                    WHERE state IN ('pending', 'access', 'reconciliation');
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, time TEXT NOT NULL, operator TEXT NOT NULL,
                    operation TEXT, action TEXT NOT NULL, detail TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_events_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT, 'Audit events cannot be edited'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_events_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT, 'Audit events cannot be deleted'); END;
                CREATE TABLE IF NOT EXISTS users (
                    name TEXT PRIMARY KEY, salt TEXT NOT NULL, digest TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','operator')));
                CREATE TABLE IF NOT EXISTS stock_items (
                    id TEXT PRIMARY KEY, compartment INTEGER NOT NULL REFERENCES compartments(id),
                    product TEXT NOT NULL, scan TEXT NOT NULL, gtin TEXT NOT NULL, serial TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS unique_package_serial ON stock_items(gtin,serial)
                    WHERE serial <> '';
                CREATE TABLE IF NOT EXISTS operation_items (
                    operation TEXT NOT NULL REFERENCES operations(id), id TEXT NOT NULL,
                    product TEXT NOT NULL, scan TEXT NOT NULL, gtin TEXT NOT NULL, serial TEXT NOT NULL,
                    PRIMARY KEY(operation,id));
                CREATE TABLE IF NOT EXISTS schema_meta (name TEXT PRIMARY KEY);
            """)
            db.executemany("INSERT OR IGNORE INTO compartments(id) VALUES (?)", [(i,) for i in range(1, 5)])
        # Existing aggregate stock stays intact. Its per-unit serials are unknown.
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM schema_meta WHERE name='box_records_v1'").fetchone():
                for row in db.execute("SELECT * FROM compartments"):
                    for _ in range(row["quantity"]):
                        db.execute("INSERT INTO stock_items VALUES (?,?,?,?,?,?)",
                                   (uuid.uuid4().hex, row["id"], row["product"], "", "", ""))
                db.execute("INSERT INTO schema_meta VALUES ('box_records_v1')")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _event(self, db, operator, operation, action, detail=""):
        return db.execute("INSERT INTO events(time,operator,operation,action,detail) VALUES (?,?,?,?,?)",
                          (timestamp(), operator, operation, action, str(detail))).lastrowid

    def record_lock_ack(self, operation, operator):
        with self.transaction() as db:
            self._operation(db, operation, operator)
            return self._event(db, operator, operation, "lock_acknowledged", "Optional lock request acknowledged")

    def users_exist(self):
        with self.connect() as db:
            return db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def start_local_session(self):
        """Explicit password-free workstation access, without impersonating a named user."""
        with self.transaction() as db:
            self._event(db, "local-workstation", None, "local_session_started",
                        "Password-free laptop session; individual operator identity is not verified")
        self.local_session = True
        return "local-workstation"

    def _role(self, db, operator, admin=False):
        if self.local_session and operator == "local-workstation":
            return
        user = db.execute("SELECT role FROM users WHERE name=?", (operator,)).fetchone()
        if not user or (admin and user[0] != "admin"):
            raise ValueError("An authorized administrator is required." if admin else "Sign in first.")

    def add_user(self, name, password, role="operator", actor=None):
        name = name.strip()
        if not name or len(name) > 80 or len(password) < 12 or role not in ("admin", "operator"):
            raise ValueError("Use a name and password of at least 12 characters; choose admin or operator.")
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 300000).hex()
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                self._role(db, actor, admin=True)
            elif role != "admin":
                raise ValueError("The first account must be an administrator.")
            try:
                db.execute("INSERT INTO users VALUES (?,?,?,?)", (name, salt, digest, role))
            except sqlite3.IntegrityError as exc:
                raise ValueError("That account already exists.") from exc
            self._event(db, actor or name, None, "account_created", f"{name}: {role}")

    def authenticate(self, name, password):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
            salt = bytes.fromhex(row["salt"]) if row else bytes(16)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300000).hex()
            ok = bool(row) and hmac.compare_digest(actual, row["digest"])
            self._event(db, name, None, "login" if ok else "login_failed")
            return row["role"] if ok else None

    def compartments(self):
        with self.connect() as db:
            db.execute("BEGIN")
            result = []
            for r in db.execute("SELECT * FROM compartments ORDER BY id"):
                items = [self._item(i) for i in db.execute("SELECT * FROM stock_items WHERE compartment=? ORDER BY id", (r["id"],))]
                result.append(dict(id=r["id"], quantity=r["quantity"], product=json.loads(r["product"]), items=items))
            return result

    @staticmethod
    def _item(row):
        result = dict(row)
        result["product"] = json.loads(result["product"])
        return result

    def operation(self, operation):
        with self.connect() as db:
            row = db.execute("SELECT * FROM operations WHERE id=?", (operation,)).fetchone()
            return dict(row) if row else None

    def reconciliation_items(self, operation):
        with self.connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT * FROM operations WHERE id=?", (operation,)).fetchone()
            if not row:
                raise ValueError("Operation does not exist.")
            items = {r["id"]: self._item(r) for r in db.execute("SELECT * FROM stock_items WHERE compartment=?", (row["compartment"],))}
            if row["kind"] == "load":
                items.update({r["id"]: self._item(r) for r in db.execute("SELECT * FROM operation_items WHERE operation=?", (operation,))})
            return sorted(items.values(), key=lambda i: (i["product"]["expiry_date"], i["id"]))

    def active(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM operations WHERE state IN ('pending','access','reconciliation')").fetchone()
            return dict(row) if row else None

    def _operation(self, db, operation, operator):
        self._role(db, operator)
        row = db.execute("SELECT * FROM operations WHERE id=?", (operation,)).fetchone()
        if not row or row["state"] not in ("pending", "access", "reconciliation"):
            raise ValueError("Operation is already completed or does not exist.")
        if row["operator"] != operator:
            self._role(db, operator, admin=True)
        return row

    def begin(self, kind, compartment, count, product, operator, reason="", items=None):
        if not isinstance(reason, str):
            raise ValueError("Provide a text reason.")
        if kind not in ("load", "dispense", "unload", "manual"):
            raise ValueError("Unsupported operation.")
        if type(compartment) is not int or compartment not in range(1, 5):
            raise ValueError("Choose compartment 1 through 4.")
        if kind in ("load", "dispense"):
            positive(count)
        if items is not None and (kind != "load" or not isinstance(items, list) or len(items) != count):
            raise ValueError("Supply one package record for each loaded unit.")
        with self.transaction() as db:
            self._role(db, operator, admin=kind in ("load", "unload", "manual"))
            if kind == "manual" and not reason.strip():
                raise ValueError("A reason is required for manual access.")
            if db.execute("SELECT 1 FROM operations WHERE state IN ('pending','access','reconciliation')").fetchone():
                raise ValueError("Complete or reconcile the outstanding operation first.")
            row = db.execute("SELECT * FROM compartments WHERE id=?", (compartment,)).fetchone()
            old = json.loads(row["product"])
            if kind == "load":
                product = medicine(product)
                keys = ("ndc", "unit", "generic_name") if items is not None else ("ndc", "lot", "expiry_date", "unit", "generic_name")
                if row["quantity"] and any(product[k] != old.get(k) for k in keys):
                    raise ValueError("Top-ups must match product, lot, expiration, name, and unit. Unload first.")
            else:
                product = old
            if kind == "dispense":
                if count > row["quantity"]:
                    raise ValueError("Insufficient stock.")
                available = [r for r in db.execute("SELECT * FROM stock_items WHERE compartment=?", (compartment,))
                             if json.loads(r["product"])["expiry_date"] >= date.today().isoformat()]
                if len(available) < count:
                    raise ValueError("Not enough unexpired stock. Unload or reconcile expired packages first.")
                # The operation snapshot describes the first eligible package.
                product = json.loads(available[0]["product"])
            if kind == "unload":
                if not row["quantity"]:
                    raise ValueError("Compartment is already empty.")
                count = row["quantity"]
            if kind == "manual":
                count = 0
            op = uuid.uuid4().hex
            db.execute("INSERT INTO operations(id,compartment,kind,requested,product,state,operator,reason,created) "
                       "VALUES (?,?,?,?,?,'pending',?,?,?)",
                       (op, compartment, kind, count, json.dumps(product), operator, reason, timestamp()))
            self._event(db, operator, op, "requested", f"{kind}: compartment {compartment}, count {count}; {reason}")
            if kind == "load":
                for item in items if items is not None else [{"product": product, "scan": ""}] * count:
                    self._stage_load(db, op, item, product)
            return op

    def _stage_load(self, db, operation, item, expected):
        if not isinstance(item, dict):
            raise ValueError("Invalid package record.")
        product = medicine(item.get("product", expected))
        if any(product[k] != expected[k] for k in ("ndc", "generic_name", "unit")):
            raise ValueError("Every package must have the same identity and counted unit.")
        scan = item.get("scan", "")
        parsed = read_scan(scan) if scan else {"gtin": "", "serial": "", "lot": "", "expiry_date": ""}
        if scan and identifier(product["ndc"]) not in aliases(parsed) and item.get("package_ndc") != identifier(product["ndc"]):
            raise ValueError("The scanned barcode does not identify this package.")
        if any(parsed[k] and parsed[k] != product[k] for k in ("lot", "expiry_date")):
            raise ValueError("Lot and expiration must match the scanned package.")
        if parsed["expiry_date"] and date.fromisoformat(parsed["expiry_date"]) <= date.today() + timedelta(days=31):
            raise ValueError("This scanned box expires within 31 days. It was not added.")
        if parsed["serial"]:
            for table in ("stock_items", "operation_items"):
                query = f"SELECT 1 FROM {table} WHERE gtin=? AND serial=?"
                if table == "operation_items":
                    query += " AND operation IN (SELECT id FROM operations WHERE state IN ('pending','access','reconciliation'))"
                if db.execute(query, (parsed["gtin"], parsed["serial"])).fetchone():
                    raise ValueError("This serialized package is already recorded. Scan a different box.")
        db.execute("INSERT INTO operation_items VALUES (?,?,?,?,?,?)",
                   (operation, uuid.uuid4().hex, json.dumps(product), scan, parsed["gtin"], parsed["serial"]))

    def add_load_item(self, operation, product, scan, operator, package_ndc=None):
        with self.transaction() as db:
            row = self._operation(db, operation, operator)
            if row["kind"] != "load" or row["state"] != "access":
                raise ValueError("No active loading session.")
            self._stage_load(db, operation, {"product": product, "scan": scan, "package_ndc": package_ndc}, json.loads(row["product"]))
            db.execute("UPDATE operations SET requested=requested+1 WHERE id=?", (operation,))
            self._event(db, operator, operation, "package_staged", scan)

    def access(self, operation, operator):
        # Persist uncertainty BEFORE requesting hardware access.
        with self.transaction() as db:
            row = self._operation(db, operation, operator)
            if row["state"] != "pending":
                raise ValueError("Access has already been requested. Do not retry; reconcile.")
            db.execute("UPDATE operations SET state='access' WHERE id=?", (operation,))
            self._event(db, operator, operation, "access_requested")

    def note_reopen(self, operation, operator):
        with self.transaction() as db:
            row = self._operation(db, operation, operator)
            if row["state"] != "access":
                raise ValueError("Only the current access operation can be reopened.")
            self._event(db, operator, operation, "explicit_reopen_requested")
            return row["compartment"]

    def verify_one(self, operation, operator, scan=None, package_ndc=None):
        with self.transaction() as db:
            row = self._operation(db, operation, operator)
            if row["kind"] != "dispense" or row["state"] != "access" or row["verified"] >= row["requested"]:
                raise ValueError("No item verification is expected.")
            product = json.loads(row["product"])
            parsed = read_scan(scan) if scan is not None else None
            if parsed and identifier(product["ndc"]) not in aliases(parsed) and identifier(package_ndc or parsed["code"]) != identifier(product["ndc"]):
                raise ValueError("This scan is a different package.")
            items = [self._item(r) for r in db.execute(
                "SELECT * FROM stock_items WHERE compartment=? AND id NOT IN (SELECT id FROM operation_items WHERE operation=?)",
                (row["compartment"], operation))]
            items.sort(key=lambda i: (i["product"]["expiry_date"], i["id"]))
            match = next((i for i in items if i["product"]["expiry_date"] >= date.today().isoformat()
                          and (not parsed or not parsed["serial"] or (i["serial"] == parsed["serial"] and i["gtin"] == parsed["gtin"]))
                          and (parsed is not None or not i["serial"])
                          and (not parsed or all(not parsed[k] or parsed[k] == i["product"][k] for k in ("lot", "expiry_date")))), None)
            if not match:
                raise ValueError("No unexpired, unverified box matches this scan and serial number.")
            db.execute("INSERT INTO operation_items VALUES (?,?,?,?,?,?)",
                       (operation, match["id"], json.dumps(match["product"]), match["scan"], match["gtin"], match["serial"]))
            db.execute("UPDATE operations SET verified=verified+1 WHERE id=?", (operation,))
            self._event(db, operator, operation, "item_verified", row["verified"] + 1)

    def cancel(self, operation, operator, reason, *, access_attempted=True):
        with self.transaction() as db:
            row = self._operation(db, operation, operator)
            state = "cancelled" if row["state"] == "pending" else "reconciliation"
            if access_attempted is False:
                if row["state"] not in ("pending", "access") or row["verified"]:
                    raise ValueError("Existing uncertain access must be reconciled.")
                state = "cancelled"
                self._event(db, operator, operation, "access_not_sent", reason)
            db.execute("UPDATE operations SET state=? WHERE id=?", (state, operation))
            self._event(db, operator, operation, state, reason)

    def finish(self, operation, operator, closed=False):
        if closed is not True:
            raise ValueError("Confirm closure before committing inventory.")
        with self.transaction() as db:
            row = self._operation(db, operation, operator)
            if row["state"] != "access" or row["kind"] == "manual":
                raise ValueError("Reconciliation is required.")
            if row["kind"] == "dispense" and row["verified"] != row["requested"]:
                raise ValueError("Not all requested items were verified; reconcile the physical count.")
            current = db.execute("SELECT quantity FROM compartments WHERE id=?", (row["compartment"],)).fetchone()[0]
            quantity = (current + row["requested"] if row["kind"] == "load" else
                        current - row["requested"] if row["kind"] == "dispense" else 0)
            if row["kind"] == "load":
                staged = list(db.execute("SELECT * FROM operation_items WHERE operation=?", (operation,)))
                for item in staged:
                    medicine(json.loads(item["product"]))
                    db.execute("INSERT INTO stock_items VALUES (?,?,?,?,?,?)",
                               (item["id"], row["compartment"], item["product"], item["scan"], item["gtin"], item["serial"]))
            elif row["kind"] == "dispense":
                # Recheck expiry at completion, including sessions crossing midnight.
                for item in db.execute("SELECT * FROM operation_items WHERE operation=?", (operation,)):
                    medicine(json.loads(item["product"]))
                db.execute("DELETE FROM stock_items WHERE id IN (SELECT id FROM operation_items WHERE operation=?)", (operation,))
            else:
                db.execute("DELETE FROM stock_items WHERE compartment=?", (row["compartment"],))
            self._commit(db, row, quantity, operator, "committed", "Closure confirmed by operator")

    def _commit(self, db, row, quantity, operator, state, reason):
        items = list(db.execute("SELECT * FROM stock_items WHERE compartment=?", (row["compartment"],)))
        if quantity != len(items):
            raise ValueError("Box records and quantity disagree. Reconcile the drawer.")
        summary = min(items, key=lambda i: json.loads(i["product"])["expiry_date"])["product"] if items else "{}"
        db.execute("UPDATE compartments SET quantity=?,product=? WHERE id=?",
                   (quantity, summary, row["compartment"]))
        db.execute("UPDATE operations SET state=? WHERE id=?", (state, row["id"]))
        self._event(db, operator, row["id"], state, f"Remaining count {quantity}. {reason}")

    def reconcile(self, operation, count, operator, reason, closed=False, remaining_ids=None):
        if type(count) is not int or count < 0 or not reason.strip() or closed is not True:
            raise ValueError("Provide a nonnegative physical count, reason, and closure confirmation.")
        with self.transaction() as db:
            self._role(db, operator, admin=True)
            row = self._operation(db, operation, operator)
            if count and not json.loads(row["product"]):
                raise ValueError("Unidentified stock cannot be reconciled. Remove it and reconcile to zero, then load it properly.")
            candidates = {r["id"]: dict(r) for r in db.execute("SELECT * FROM stock_items WHERE compartment=?", (row["compartment"],))}
            if row["kind"] == "load":
                candidates.update({r["id"]: dict(r) for r in db.execute("SELECT * FROM operation_items WHERE operation=?", (operation,))})
            if remaining_ids is not None:
                if not isinstance(remaining_ids, list) or len(remaining_ids) != count or len(set(remaining_ids)) != count or any(i not in candidates for i in remaining_ids):
                    raise ValueError("Select each recorded box that is physically present exactly once.")
                kept = [candidates[i] for i in remaining_ids]
            else:
                if count and (any(i["serial"] for i in candidates.values()) or len({i["product"] for i in candidates.values()}) > 1):
                    raise ValueError("Select the remaining box records when serial numbers or mixed lots are present.")
                kept = list(candidates.values())[:count]
                while len(kept) < count:
                    kept.append(dict(id=uuid.uuid4().hex, product=row["product"], scan="", gtin="", serial=""))
            db.execute("DELETE FROM stock_items WHERE compartment=?", (row["compartment"],))
            for item in kept:
                db.execute("INSERT INTO stock_items VALUES (?,?,?,?,?,?)",
                           (item["id"], row["compartment"], item["product"], item["scan"], item["gtin"], item["serial"]))
            self._commit(db, row, count, operator, "reconciled", reason)

    def audit(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events ORDER BY id")]

    def backup(self, destination):
        destination = Path(destination)
        if destination.resolve() == self.path.resolve() or destination.exists():
            raise ValueError("Choose a new backup filename outside the active database.")
        with self.connect() as source, sqlite3.connect(destination, factory=ClosingConnection) as target:
            source.backup(target)
