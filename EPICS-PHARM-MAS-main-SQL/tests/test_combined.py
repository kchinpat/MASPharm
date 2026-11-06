"""Cross-interface regressions for the combined package-tracking workflows."""
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from datetime import date, datetime, timedelta

from pharm import activity
from pharm.barcodes import read_scan, expiry_date, drug_ndc
from pharm.catalog import Catalog, identifier
from pharm.hardware import Simulator, Result
from pharm.store import Store
from pharm.team_hardware import TeamSerialHardware
from pharm.web import create_app
from pharm.workflows import WorkflowService
from pharm.photos import fetch_photo, cached, searchable, OfficialRedirects
from test_inventory import PRODUCT

GTIN = "00001234567895"


def barcode(serial="BOX1", lot="DEMO-LOT", expiry="991231"):
    return f"(01){GTIN}(21){serial}(17){expiry}(10){lot}"


class BarcodeTests(unittest.TestCase):
    def test_team_labels_with_unseparated_serial_expiration_and_lot(self):
        scan = read_scan("0100359651029886217AYN7S3AXN4YG6K1728043010CYAZES25035A")
        self.assertEqual("00359651029886", scan["gtin"])
        self.assertEqual("7AYN7S3AXN4YG6K", scan["serial"])
        self.assertEqual("2028-04-30", scan["expiry_date"])
        self.assertEqual("CYAZES25035A", scan["lot"])

    def test_fnc1_handles_ai_digits_inside_a_serial(self):
        scan = read_scan(f"]d201{GTIN}21SN1727010110INSIDE\x1d1799123110LOT17")
        self.assertEqual("SN1727010110INSIDE", scan["serial"])
        self.assertEqual("LOT17", scan["lot"])

    def test_parenthesized_fields_in_different_order(self):
        scan = read_scan(f"(01){GTIN}(10)LOT21ABC(17)280200(21)SERIAL17")
        self.assertEqual("2028-02-29", scan["expiry_date"])
        self.assertEqual("LOT21ABC", scan["lot"])
        self.assertEqual("SERIAL17", scan["serial"])

    def test_month_end_and_invalid_dates(self):
        self.assertEqual("2027-02-28", expiry_date("270200"))
        for exp in ("271300", "270230", "short", "2701000"):
            with self.subTest(exp=exp), self.assertRaises(ValueError):
                expiry_date(exp)

    def test_incomplete_repeated_and_unsupported_fields_rejected(self):
        for value in ("(01)0035", f"(01){GTIN}(99)X", f"(01){GTIN}(17)991231(17)991231", "]d217991231", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_scan(value)

    def test_numeric_identifiers_keep_leading_zeros(self):
        self.assertEqual("001234", read_scan("00-1234")["code"])

    def test_drug_ndc_needs_the_drug_range_indicator_0_and_a_valid_check_digit(self):
        for code in ("359651029886", "0359651029886", "00359651029886"):
            with self.subTest(code=code):
                self.assertEqual("5965102988", drug_ndc(code))
        for code in ("359651029887", "10359651029883", GTIN, "3596510298", "3359651029886"):
            with self.subTest(code=code):
                self.assertEqual("", drug_ndc(code))


class CombinedFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "stock.sqlite3"
        self.store = Store(self.path)
        path = self.directory / "catalog.json"
        path.write_text(json.dumps([{"generic_name": PRODUCT["generic_name"],
                                    "packaging": [{"package_ndc": PRODUCT["ndc"]}],
                                    "openfda": {"upc": ["001234567895"]}}]))
        self.catalog = Catalog(path)
        self.hardware = Simulator()
        self.service = WorkflowService(self.store, self.catalog, self.hardware)
        self.actor = self.service.operator

    def start_box(self, serial="BOX1", lot="DEMO-LOT", expiry="2099-12-31"):
        scan = barcode(serial, lot, expiry.replace("-", "")[2:])
        product = {**PRODUCT, "lot": lot, "expiry_date": expiry}
        return self.service.start("load", 1, 1, product, scan)

    def complete(self, op):
        self.service.finish(op["id"], placed=True, closed=True)


class ActivityTests(CombinedFixture):
    """UI two's recent activity: what happened to the stock, in plain words."""

    def lines(self):
        return [line["text"] for line in activity.recent(self.store, 10)]

    def stocked(self, count=2):
        operation = self.store.begin("load", 1, count, PRODUCT, self.actor)
        self.store.access(operation, self.actor)
        self.store.finish(operation, self.actor, closed=True)

    def test_sessions_and_steps_within_an_operation_never_show(self):
        self.assertEqual([], self.lines())  # the store's session started, and nothing has happened yet
        operation = self.start_box()
        self.assertEqual([], self.lines())  # requested, staged and unlocked, but not finished
        self.complete(operation)
        self.assertEqual([f"Loaded 1 bottle of {PRODUCT['generic_name']} into drawer 1"], self.lines())
        text = " ".join(self.lines())
        for hidden in ("local-workstation", "operator", "session", "compartment", "Closure"):
            self.assertNotIn(hidden, text)

    def test_dispensing_and_emptying_read_as_what_was_removed(self):
        self.stocked()
        operation = self.store.begin("dispense", 1, 1, {}, self.actor)
        self.store.access(operation, self.actor)
        self.store.verify_one(operation, self.actor)
        self.store.finish(operation, self.actor, closed=True)
        self.assertEqual(f"Dispensed 1 bottle of {PRODUCT['generic_name']} from drawer 1", self.lines()[0])
        operation = self.store.begin("unload", 1, 0, {}, self.actor)
        self.store.access(operation, self.actor)
        self.store.finish(operation, self.actor, closed=True)
        self.assertEqual(f"Emptied drawer 1 (1 bottle of {PRODUCT['generic_name']})", self.lines()[0])

    def test_an_interruption_needs_attention_until_the_drawer_is_counted(self):
        self.stocked()
        operation = self.store.begin("dispense", 1, 1, {}, self.actor)
        self.store.access(operation, self.actor)
        self.store.cancel(operation, self.actor, "Cancelled after drawer access")
        newest = activity.recent(self.store, 1)[0]
        self.assertEqual(("Dispensing from drawer 1 was interrupted. It needs a count.", True), (newest["text"], newest["attention"]))
        self.store.reconcile(operation, 2, self.actor, "Nothing taken", closed=True)
        counted, interrupted = activity.recent(self.store, 2)
        self.assertEqual(f"Counted drawer 1: 2 bottles of {PRODUCT['generic_name']}", counted["text"])
        self.assertFalse(interrupted["attention"])

    def test_unlocking_by_hand_shows_the_reason(self):
        operation = self.store.begin("manual", 2, 0, {}, self.actor, "Inspect")
        self.store.access(operation, self.actor)
        self.store.cancel(operation, self.actor, "Manual inspection requires a count")
        self.assertEqual("Drawer 2 was unlocked by hand (Inspect). It needs a count.", self.lines()[0])
        self.store.reconcile(operation, 0, self.actor, "", closed=True)
        self.assertEqual("Counted drawer 2: empty", self.lines()[0])

    def test_a_drawer_that_did_not_unlock_is_one_line(self):
        self.stocked()
        operation = self.store.begin("dispense", 1, 1, {}, self.actor)
        self.store.cancel(operation, self.actor, "Firmware did not acknowledge command 0: timeout", access_attempted=False)
        self.assertEqual("Drawer 1 did not unlock, so nothing changed", self.lines()[0])
        self.assertEqual(2, len(self.lines()))

    def test_reopening_is_shown(self):
        self.stocked()
        operation = self.store.begin("dispense", 1, 1, {}, self.actor)
        self.store.access(operation, self.actor)
        self.store.note_reopen(operation, self.actor)
        self.assertEqual("Drawer 1 unlocked again", self.lines()[0])

    def test_times_show_their_day_unless_today(self):
        now = datetime(2026, 11, 6, 15, 0).astimezone()
        for moment, shown in ((now.replace(hour=9, minute=5), "09:05"), (now.replace(hour=9, minute=5) - timedelta(days=1), "Yesterday 09:05"),
                              (now.replace(hour=9, minute=5) - timedelta(days=3), "3 Nov 09:05")):
            with self.subTest(shown=shown):
                self.assertEqual(shown, activity.when(moment.isoformat(), now))


class CombinedTests(CombinedFixture):
    def test_strength_is_read_from_the_catalog_for_display_only(self):
        path = self.directory / "strengths.json"
        path.write_text(json.dumps([
            {"generic_name": "A", "active_ingredients": [{"strength": ".25 mg/1"}], "packaging": [{"package_ndc": "11111-111-11"}]},
            {"generic_name": "B", "active_ingredients": [{"strength": "5 mg/1"}, {"strength": "325 mg/1"}], "packaging": [{"package_ndc": "22222-222-22"}]},
            {"generic_name": "C", "active_ingredients": [{"strength": "10 mg/mL"}], "packaging": [{"package_ndc": "33333-333-33"}]},
            {"generic_name": "D", "active_ingredients": [{"strength": "1 mg/1"}], "packaging": [{"package_ndc": "44444-444-44"}]},
            {"generic_name": "D", "active_ingredients": [{"strength": "2 mg/1"}], "packaging": [{"package_ndc": "44444-444-44"}]},
            {"generic_name": "E", "packaging": [{"package_ndc": "55555-555-55"}]}]))
        catalog = Catalog(path)
        for ndc, strength in (("11111-111-11", "0.25 mg"), ("22222-222-22", "5 mg / 325 mg"), ("33333-333-33", "10 mg/mL"),
                              ("44444-444-44", ""), ("55555-555-55", ""), ("99999-999-99", ""), ("not an id", "")):
            with self.subTest(ndc=ndc):
                self.assertEqual(strength, catalog.strength(ndc))
        self.assertNotIn("strength", catalog.loading_details("11111-111-11")[0])

    def test_gs1_maps_only_through_exact_catalog_aliases(self):
        self.assertEqual(PRODUCT["ndc"], self.catalog.lookup(barcode())["ndc"])
        self.assertTrue(self.catalog.matches(barcode(), PRODUCT["ndc"]))
        self.assertFalse(self.catalog.matches(barcode(), "123456789"))

    def test_scan_supplies_actual_lot_and_expiry(self):
        preview = self.service.preview(barcode())
        self.assertEqual("DEMO-LOT", preview["product"]["lot"])
        self.assertEqual("2099-12-31", preview["product"]["expiry_date"])
        self.assertEqual("BOX1", preview["scan"]["serial"])

    def test_drug_barcode_preview_fills_medication_and_unit_then_loads(self):
        path = self.directory / "described.json"
        path.write_text(json.dumps([{"generic_name": PRODUCT["generic_name"],
                                     "packaging": [{"package_ndc": PRODUCT["ndc"], "description": "1 TUBE in 1 CARTON (01234-5678-9)"}]}]))
        self.service.catalog = Catalog(path)
        scan = "(01)00301234567896(21)RX1(17)991231(10)RX-LOT"
        product = self.service.preview(scan)["product"]
        self.assertEqual((PRODUCT["generic_name"], "carton", PRODUCT["ndc"]), (product["generic_name"], product["unit"], product["ndc"]))
        self.complete(self.service.start("load", 1, 1, product, scan))
        drawer = self.store.compartments()[0]
        self.assertEqual((1, "carton", "RX1"), (drawer["quantity"], drawer["product"]["unit"], drawer["items"][0]["serial"]))

    def test_mixed_lots_stay_pending_until_confirmed_and_show_earliest(self):
        op = self.start_box()
        self.service.add(op["id"], {**PRODUCT, "lot": "OTHER", "expiry_date": "2098-12-31"}, barcode("BOX2", "OTHER", "981231"))
        self.assertEqual(0, self.store.compartments()[0]["quantity"])
        self.complete(op)
        drawer = self.store.compartments()[0]
        self.assertEqual(2, drawer["quantity"])
        self.assertEqual("2098-12-31", drawer["product"]["expiry_date"])
        self.assertEqual({"BOX1", "BOX2"}, {i["serial"] for i in drawer["items"]})

    def test_same_serial_cannot_be_loaded_twice_in_one_session(self):
        op = self.start_box()
        with self.assertRaisesRegex(ValueError, "already recorded"):
            self.service.add(op["id"], PRODUCT, barcode())
        self.assertEqual(1, self.store.operation(op["id"])["requested"])

    def test_same_serial_cannot_be_loaded_again_from_stock(self):
        self.complete(self.start_box())
        with self.assertRaisesRegex(ValueError, "already recorded"):
            self.start_box()
        self.assertIsNone(self.store.active())
        self.assertEqual(1, self.store.compartments()[0]["quantity"])

    def test_scanned_metadata_cannot_be_overridden(self):
        for product in ({**PRODUCT, "lot": "DIFFERENT"}, {**PRODUCT, "expiry_date": "2098-01-01"}):
            with self.subTest(product=product), self.assertRaises(ValueError):
                self.service.start("load", 1, 1, product, barcode())
        self.assertIsNone(self.store.active())

    def test_unknown_serial_is_rejected_and_duplicate_verification_is_rejected(self):
        self.complete(self.start_box())
        self.complete(self.start_box("BOX2"))
        op = self.service.start("dispense", 1, 2)
        with self.assertRaises(ValueError):
            self.service.verify(op["id"], barcode("UNKNOWN"))
        self.service.verify(op["id"], barcode())
        with self.assertRaises(ValueError):
            self.service.verify(op["id"], barcode())
        self.assertEqual(1, self.store.active()["verified"])

    def test_exact_box_is_removed_and_remaining_expiration_recomputed(self):
        self.complete(self.start_box("BOX1", "EARLY", "2098-12-31"))
        self.complete(self.start_box("BOX2", "LATER", "2099-12-31"))
        op = self.service.start("dispense", 1, 1)
        self.service.verify(op["id"], barcode("BOX1", "EARLY", "981231"))
        self.complete(op)
        drawer = self.store.compartments()[0]
        self.assertEqual(["BOX2"], [i["serial"] for i in drawer["items"]])
        self.assertEqual("2099-12-31", drawer["product"]["expiry_date"])

    def test_partial_dispense_survives_restart_and_reconciles_selected_boxes(self):
        self.complete(self.start_box())
        self.complete(self.start_box("BOX2"))
        op = self.service.start("dispense", 1, 2)
        self.service.verify(op["id"], barcode())
        self.service.cancel(op["id"], "Second scan cancelled")
        other = Store(self.path)
        actor = other.start_local_session()
        self.assertEqual(1, other.active()["verified"])
        with self.assertRaises(ValueError):
            other.begin("manual", 2, 0, {}, actor, "Blocked while uncertain")
        choices = other.reconciliation_items(op["id"])
        ids = [i["id"] for i in choices if i["serial"] == "BOX2"]
        with self.assertRaises(ValueError):
            other.reconcile(op["id"], 1, actor, "Count alone cannot identify the box", closed=True)
        other.reconcile(op["id"], 1, actor, "Only BOX2 remains", closed=True, remaining_ids=ids)
        self.assertEqual("BOX2", other.compartments()[0]["items"][0]["serial"])

    def test_interrupted_load_can_reconcile_only_boxes_placed(self):
        op = self.start_box()
        self.service.add(op["id"], PRODUCT, barcode("BOX2"))
        self.service.cancel(op["id"], "Only the first box was placed")
        selected = [i["id"] for i in self.store.reconciliation_items(op["id"]) if i["serial"] == "BOX1"]
        self.service.reconcile(op["id"], 1, "Counted BOX1 only", closed=True, remaining_ids=selected)
        self.assertEqual(["BOX1"], [i["serial"] for i in self.store.compartments()[0]["items"]])

    def test_lock_failure_does_not_block_load_dispense_or_unload(self):
        self.hardware.lock = lambda: Result(False, "No lock acknowledgement")
        load = self.start_box()
        result = self.service.finish(load["id"], placed=True, closed=True)
        self.assertFalse(result.ok)
        self.assertEqual(1, self.store.compartments()[0]["quantity"])
        dispense = self.service.start("dispense", 1, 1)
        self.service.verify(dispense["id"], barcode())
        self.service.finish(dispense["id"], placed=True, closed=True)
        self.assertEqual(0, self.store.compartments()[0]["quantity"])
        self.complete(self.start_box("BOX2"))
        unload = self.service.start("unload", 1)
        self.service.finish(unload["id"], placed=True, closed=True)
        self.assertEqual(0, self.store.compartments()[0]["quantity"])
        self.assertIsNone(self.store.active())

    def test_closure_and_contents_still_required_without_security_confirmation(self):
        op = self.start_box()
        for flags in ({"placed": True}, {"closed": True}):
            with self.assertRaises(ValueError):
                self.service.finish(op["id"], **flags)
        self.assertEqual(0, self.store.compartments()[0]["quantity"])
        self.service.finish(op["id"], placed=True, closed=True)
        self.assertEqual(1, self.store.compartments()[0]["quantity"])

    def test_reconciliation_commits_even_when_lock_request_raises(self):
        op = self.start_box()
        self.service.cancel(op["id"], "Interrupted placement")
        selected = [i["id"] for i in self.store.reconciliation_items(op["id"])]
        self.hardware.lock = Mock(side_effect=OSError("Disconnected"))
        result = self.service.reconcile(op["id"], 1, "Box present", closed=True, remaining_ids=selected)
        self.assertFalse(result.ok)
        self.assertEqual(1, self.store.compartments()[0]["quantity"])
        self.assertIsNone(self.store.active())

    def test_reopening_is_explicit_and_audited(self):
        op = self.start_box()
        self.service.reopen(op["id"])
        self.assertIn("explicit_reopen_requested", [e["action"] for e in self.store.audit()])
        self.assertEqual(op["id"], self.store.active()["id"])

    def test_scanned_near_expiry_box_is_not_added(self):
        expires = (date.today() + timedelta(days=10)).isoformat()
        with self.assertRaisesRegex(ValueError, "31 days"):
            self.start_box(expiry=expires)
        self.assertIsNone(self.store.active())

    def test_expired_box_cannot_be_verified_but_fresh_box_in_same_drawer_can(self):
        self.complete(self.start_box())
        self.complete(self.start_box("BOX2"))
        with self.store.transaction() as db:
            item = db.execute("SELECT * FROM stock_items WHERE serial='BOX1'").fetchone()
            product = json.loads(item["product"])
            product["expiry_date"] = "2000-01-01"
            db.execute("UPDATE stock_items SET product=? WHERE id=?", (json.dumps(product), item["id"]))
        with self.assertRaises(ValueError):
            self.service.start("dispense", 1, 2)
        op = self.service.start("dispense", 1, 1)
        with self.assertRaises(ValueError):
            self.service.verify(op["id"], barcode())
        self.service.verify(op["id"], barcode("BOX2"))

    def test_backup_contains_individual_box_records(self):
        self.complete(self.start_box())
        path = self.directory / "backup.sqlite3"
        self.store.backup(path)
        self.assertEqual(self.store.compartments(), Store(path).compartments())

    def test_existing_aggregate_database_is_migrated_without_stock_loss(self):
        path = self.directory / "old.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE compartments (id INTEGER PRIMARY KEY, quantity INTEGER NOT NULL, product TEXT NOT NULL)")
            db.execute("INSERT INTO compartments VALUES (1,3,?)", (json.dumps(PRODUCT),))
        db.close()
        migrated = Store(path)
        self.assertEqual(3, migrated.compartments()[0]["quantity"])
        self.assertEqual(3, len(migrated.compartments()[0]["items"]))
        self.assertEqual(3, len(Store(path).compartments()[0]["items"]))


class BrowserTests(CombinedFixture):
    def setUp(self):
        super().setUp()
        self.app = create_app(self.store, self.catalog, self.hardware)
        self.client = self.app.test_client()
        self.addCleanup(self.app.extensions["photos"].shutdown, wait=True)
        self.download = patch("pharm.web.fetch_photo", side_effect=ValueError("No photo in tests.")).start()
        self.addCleanup(patch.stopall)
        page = self.client.get("/").get_data(as_text=True)
        self.token = page.split('const token = "', 1)[1].split('"', 1)[0]

    def post(self, path, data):
        return self.client.post(path, json=data, headers={"X-Pharm-Token": self.token})

    def photo_downloads_finish(self):
        self.app.extensions["photos"].submit(lambda: None).result(timeout=5)  # queued behind them

    def test_find_tells_a_new_package_from_a_stocked_one_and_a_bad_scan(self):
        self.assertEqual([], self.post("/api/find", {"scan": PRODUCT["ndc"]}).json["drawers"])
        self.complete(self.start_box())
        self.assertEqual([1], self.post("/api/find", {"scan": PRODUCT["ndc"]}).json["drawers"])
        self.assertEqual([], self.post("/api/find", {"scan": "9999999999"}).json["drawers"])
        for scan in ("", "not a barcode"):
            self.assertEqual(409, self.post("/api/find", {"scan": scan}).status_code)

    def test_state_downloads_a_missing_label_photo_in_the_background(self):
        release = threading.Event()

        def download(directory, code):
            release.wait(5)
            path = Path(directory) / (identifier(code) + ".gif")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"GIF89a")
            return path
        self.download.side_effect = download
        self.complete(self.start_box())
        drawer = self.client.get("/api/state").json["drawers"][0]
        self.assertEqual((None, "loading"), (drawer["photo"], drawer["photo_status"]))
        self.assertIsNone(self.client.get("/api/state").json["drawers"][1]["photo_status"])
        release.set()
        self.photo_downloads_finish()
        drawer = self.client.get("/api/state").json["drawers"][0]
        self.assertEqual(("/images/0123456789.gif", None), (drawer["photo"], drawer["photo_status"]))
        self.download.assert_called_once()

    def test_failed_label_photo_is_not_retried_until_asked(self):
        self.complete(self.start_box())
        self.client.get("/api/state")
        self.photo_downloads_finish()
        self.assertEqual("failed", self.client.get("/api/state").json["drawers"][0]["photo_status"])
        self.assertEqual(1, self.download.call_count)
        self.assertEqual(200, self.post("/api/photo/1", {}).status_code)
        self.photo_downloads_finish()
        self.assertEqual(2, self.download.call_count)

    def test_browser_load_does_not_commit_before_closure_then_desktop_sees_boxes(self):
        response = self.post("/api/start", {"kind":"load", "drawer":1, "count":1, "product":PRODUCT, "scan":barcode()})
        self.assertEqual(200, response.status_code)
        op = response.json["operation"]["id"]
        self.assertEqual(0, Store(self.path).compartments()[0]["quantity"])
        self.assertEqual(409, self.post("/api/finish", {"operation":op,"placed":True}).status_code)
        self.hardware.lock = lambda: Result(False, "No acknowledgement")
        response = self.post("/api/finish", {"operation":op,"placed":True,"closed":True})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json["ok"])
        self.assertFalse(response.json["lock_ok"])
        self.assertEqual("BOX1", Store(self.path).compartments()[0]["items"][0]["serial"])

    def test_cross_origin_and_missing_token_cannot_actuate(self):
        data = {"kind":"manual","drawer":1,"reason":"Test"}
        self.assertEqual(403, self.client.post("/api/start", json=data).status_code)
        self.assertEqual(403, self.client.post("/api/start", json=data, headers={"X-Pharm-Token":self.token,"Origin":"https://untrusted.example"}).status_code)
        self.assertEqual(403, self.client.get("/api/state", headers={"Host":"untrusted.example"}).status_code)
        self.assertIsNone(self.hardware.selected)

    def test_browser_unlock_without_reason_saves_entered_count(self):
        self.complete(self.service.start("load", 1, 3, PRODUCT))
        response = self.post("/api/start", {"kind": "manual", "drawer": 1})
        self.assertEqual(200, response.status_code)
        op = response.json["operation"]
        self.assertEqual("", op["reason"])
        response = self.post("/api/reconcile", {"operation": op["id"], "count": 5, "closed": True})
        self.assertEqual(200, response.status_code)
        self.assertEqual(5, Store(self.path).compartments()[0]["quantity"])
        self.assertIsNone(self.store.active())

    def test_bad_types_and_invalid_drawers_never_change_stock(self):
        for data in ({"kind":"load","drawer":True,"count":1,"product":PRODUCT},
                     {"kind":"load","drawer":5,"count":1,"product":PRODUCT},
                     {"kind":"load","drawer":1,"count":True,"product":PRODUCT},
                     {"kind":"load","drawer":1,"count":1,"product":[]},
                     {"kind":"manual","drawer":1,"reason":[]},
                     {"kind":"manual","drawer":1,"reason":None}):
            with self.subTest(data=data):
                self.assertEqual(409, self.post("/api/start", data).status_code)
        self.assertIsNone(self.store.active())
        self.assertIsNone(self.hardware.selected)

    def test_unknown_catalog_scan_keeps_manual_entry_available(self):
        response = self.post("/api/preview", {"scan":"000999"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("000999", response.json["product"]["ndc"])
        self.assertIn("manually", response.json["notice"])

    def test_bad_catalog_upload_preserves_current_catalog(self):
        response = self.client.post("/api/catalog", data={"catalog":(io.BytesIO(b"{}"),"bad.json")}, headers={"X-Pharm-Token":self.token})
        self.assertEqual(409, response.status_code)
        self.assertIs(self.catalog, self.app.extensions["pharm"].catalog)

    def test_page_starts_on_ui_two_in_dark_and_offers_light_and_the_legacy_ui(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn('<html lang="en" data-ui="two" data-theme="dark">', page)
        self.assertIn(">Light theme</button>", page)
        self.assertIn(">Switch to legacy UI</button>", page)
        self.assertIn('localStorage.getItem("pharm-ui") === "one"', page)
        self.assertIn('"pharm-ui-two-theme"', page)  # its theme is remembered apart from the legacy UI's

    def test_stylesheet_has_a_light_theme_for_ui_two(self):
        css = self.client.get("/cabinet.css").get_data(as_text=True)
        self.assertIn(':root[data-ui="two"][data-theme="light"] {', css)
        self.assertNotIn("#theme-button { display: none; }", css)

    def test_state_carries_strength_and_the_newest_events_first(self):
        path = self.directory / "strength.json"
        path.write_text(json.dumps([{"generic_name": PRODUCT["generic_name"], "active_ingredients": [{"strength": "5 mg/1"}],
                                     "packaging": [{"package_ndc": PRODUCT["ndc"]}]}]))
        self.app.extensions["pharm"].catalog = Catalog(path)
        self.complete(self.start_box())
        state = self.client.get("/api/state").json
        self.assertEqual(("5 mg", ""), (state["drawers"][0]["strength"], state["drawers"][1]["strength"]))
        self.assertEqual([f"Loaded 1 bottle of {PRODUCT['generic_name']} into drawer 1"], [a["text"] for a in state["activity"]])
        self.assertEqual({"when", "text", "attention"}, set(state["activity"][0]))
        self.assertEqual("5 mg", self.post("/api/preview", {"scan": PRODUCT["ndc"]}).json["strength"])

    def test_verify_reports_the_scanned_serial(self):
        self.complete(self.start_box())
        op = self.service.start("dispense", 1, 1)
        self.assertEqual("BOX1", self.post("/api/verify", {"operation": op["id"], "scan": barcode()}).json["serial"])

    def test_audit_and_backup_are_downloadable(self):
        self.complete(self.start_box())
        audit = self.client.get("/api/audit")
        self.assertEqual(200, audit.status_code)
        self.assertIn("committed", audit.get_data(as_text=True))
        response = self.client.get("/api/backup")
        self.assertTrue(response.data.startswith(b"SQLite format 3"))

    def test_duplicate_completion_and_overlapping_interface_operations_rejected(self):
        self.complete(self.start_box())
        op = self.service.start("dispense", 1, 1)
        self.assertEqual(409, self.post("/api/start", {"kind":"manual","drawer":2,"reason":"Overlap"}).status_code)
        self.assertEqual(409, self.post("/api/finish", {"operation":op["id"],"placed":True,"closed":True,"secured":True}).status_code)
        self.service.verify(op["id"], barcode())
        self.complete(op)
        self.assertEqual(409, self.post("/api/finish", {"operation":op["id"],"placed":True,"closed":True,"secured":True}).status_code)


class FakeUart:
    """Answers each written command with its queued reply. Reading more bytes
    than have arrived stands for waiting out the serial read timeout."""

    def __init__(self, replies):
        self.is_open = True
        self.replies = list(replies)
        self.pending = b""
        self.writes = []
        self.timeouts = 0

    def reset_input_buffer(self):
        self.pending = b""

    def write(self, data):
        self.writes.append(bytes(data))
        self.pending += self.replies.pop(0) if self.replies else b""
        return len(data)

    def flush(self):
        pass

    @property
    def in_waiting(self):
        return len(self.pending)

    def read(self, size=1):
        if size > len(self.pending):
            self.timeouts += 1
        data, self.pending = self.pending[:size], self.pending[size:]
        return data

    def close(self):
        self.is_open = False


class TeamAdapterTests(unittest.TestCase):
    def uart(self, replies):
        return FakeUart(replies)

    def test_adapter_is_lazy_and_requires_status_before_actuating(self):
        uart = self.uart([b"\x00",b"\x20",b"\x01"])
        factory = Mock(return_value=uart)
        adapter = TeamSerialHardware("COM9", factory)
        factory.assert_not_called()
        self.assertTrue(adapter.open(1).ok)
        self.assertEqual([b"\x30",b"\x20",b"\x01"], uart.writes)

    def test_replies_are_taken_without_waiting_out_the_read_timeout(self):
        # Each reply is one byte; asking for more stalled every command by the
        # full timeout, so the drawer's release ended before the screen said open.
        uart = self.uart([b"\x00",b"\x20",b"\x01",b"\x01",b"\x07",b"\x00"])
        adapter = TeamSerialHardware("COM9", lambda:uart)
        self.assertTrue(adapter.open(1).ok)
        self.assertTrue(adapter.lock().ok)
        self.assertTrue(adapter.status().ok)
        self.assertEqual(0, uart.timeouts)

    def test_mas1_text_is_rejected_before_any_actuator_command(self):
        uart = self.uart([b"MAS/1 ERR UNKNOWN\r\n"])
        result = TeamSerialHardware("COM9", lambda:uart).open(1)
        self.assertFalse(result.ok)
        self.assertFalse(result.action_attempted)
        self.assertEqual([b"\x30"], uart.writes)

    def test_lost_unlock_echo_is_never_retried(self):
        uart = self.uart([b"\x00",b"\x20",b""])
        result = TeamSerialHardware("COM9", lambda:uart).open(1)
        self.assertFalse(result.ok)
        self.assertTrue(result.action_attempted)
        self.assertEqual(1, uart.writes.count(b"\x01"))

    def test_status_exposes_output_levels_without_claiming_physical_closure(self):
        uart = self.uart([b"\x21"])
        adapter = TeamSerialHardware("COM9", lambda:uart)
        self.assertTrue(adapter.status().ok)
        self.assertEqual([1], adapter.open_drawers)
        self.assertEqual([2], adapter.output_unlocked)


class PhotoTests(unittest.TestCase):
    def test_optional_photo_download_is_bounded_and_cached_by_safe_identifier(self):
        page = Mock()
        page.__enter__ = Mock(return_value=page)
        page.__exit__ = Mock(return_value=False)
        page.read.return_value = b'<div class="drug-photos"><img src="/images/package.jpg"></div>'
        photo = Mock()
        photo.__enter__ = Mock(return_value=photo)
        photo.__exit__ = Mock(return_value=False)
        photo.read.return_value = b"\xff\xd8\xffSYNTHETIC"
        opener = Mock()
        opener.open.side_effect = [page, photo]
        with tempfile.TemporaryDirectory() as directory, patch("pharm.photos.build_opener", return_value=opener):
            path = fetch_photo(directory, "00-123")
            self.assertEqual("00123.jpg", path.name)
            self.assertEqual(path, cached(directory, "00123"))
            self.assertEqual(5, opener.open.call_args.kwargs["timeout"])

    def test_bundled_photos_keep_hyphenated_names_and_match_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "0406-0512-01.jpg").write_bytes(b"\xff\xd8\xffSYNTHETIC")
            Path(directory, "0406-0512-1.jpg").write_bytes(b"\xff\xd8\xffSYNTHETIC")
            self.assertEqual("0406-0512-01.jpg", cached(directory, "0406-0512-01").name)
            self.assertEqual("0406-0512-01.jpg", cached(directory, "0406051201").name)
            self.assertEqual("0406-0512-1.jpg", cached(directory, "040605121").name)
            self.assertIsNone(cached(directory, "04060512"))
            self.assertIsNone(cached(Path(directory) / "absent", "0406051201"))

    def test_photo_search_uses_the_ndc_inside_a_drug_gtin(self):
        self.assertEqual("5965102988", searchable("00359651029886"))
        self.assertEqual("59651-029-88", searchable("59651-029-88"))
        self.assertEqual("00012345678905", searchable("00012345678905"))

    def test_photo_cache_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            cached(".", "../private")

    def test_photo_redirects_cannot_leave_the_official_host(self):
        with self.assertRaises(ValueError):
            OfficialRedirects().redirect_request(None, None, 302, "", {}, "https://untrusted.example/photo.jpg")


if __name__ == "__main__":
    unittest.main()
