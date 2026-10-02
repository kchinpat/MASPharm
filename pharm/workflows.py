"""Browser workflow service backed by the same durable store as the desktop."""
import threading
from .barcodes import read_scan
from .catalog import identifier
from .store import medicine


class WorkflowService:
    def __init__(self, store, catalog, hardware):
        self.store, self.catalog, self.hardware = store, catalog, hardware
        self.operator = store.start_local_session()
        self.lock = threading.RLock()

    @staticmethod
    def device(action):
        try:
            return action()
        except Exception as exc:
            from .hardware import Result
            return Result(False, str(exc))

    def preview(self, scan):
        parsed = read_scan(scan)
        product, notice = self.catalog.loading_details(scan)
        product.setdefault("unit", "box")
        return {"product": product, "scan": parsed, "notice": notice}

    def _package(self, product, scan):
        product = medicine(product)
        if scan and not self.catalog.matches(scan, product["ndc"]):
            raise ValueError("The scanned package does not match the entered identity.")
        return product

    def start(self, kind, number, count=0, product=None, scan="", reason=""):
        with self.lock:
            items = None
            if kind == "load":
                product = self._package(product or {}, scan)
                if scan:
                    if count != 1:
                        raise ValueError("Start with one scanned box, then scan each additional box.")
                    items = [{"product": product, "scan": scan, "package_ndc": identifier(product["ndc"])}]
            op = self.store.begin(kind, number, count, product or {}, self.operator, reason, items=items)
            self.store.access(op, self.operator)
            try:
                result = self.hardware.open(number)
            except Exception as exc:
                from .hardware import Result
                result = Result(False, str(exc))
            if not result.ok:
                self.store.cancel(op, self.operator, result.message, access_attempted=result.action_attempted)
                raise ValueError(result.message)
            return self.store.operation(op)

    def verify(self, op, scan):
        with self.lock:
            row = self.store.operation(op)
            if not row:
                raise ValueError("No such operation.")
            import json
            package = json.loads(row["product"])["ndc"]
            if not self.catalog.matches(scan, package):
                raise ValueError("This box has a different package identity.")
            self.store.verify_one(op, self.operator, scan, package_ndc=identifier(package))
            return self.store.operation(op)

    def reopen(self, op):
        with self.lock:
            number = self.store.note_reopen(op, self.operator)
            result = self.device(lambda: self.hardware.open(number))
            if not result.ok:
                self.store.cancel(op, self.operator, result.message)
                raise ValueError(result.message)

    def add(self, op, product, scan):
        with self.lock:
            product = self._package(product, scan)
            self.store.add_load_item(op, product, scan, self.operator, package_ndc=identifier(product["ndc"]))
            return self.store.operation(op)

    def finish(self, op, placed=False, closed=False):
        with self.lock:
            row = self.store.operation(op)
            if not row or row["state"] != "access" or row["kind"] == "manual":
                raise ValueError("This operation requires reconciliation.")
            if placed is not True or closed is not True:
                raise ValueError("Confirm the physical count and closure before saving.")
            self.store.finish(op, self.operator, closed=True)
            return self.device(self.hardware.lock)

    def secure(self, op):
        """Optional lock request, independent of inventory completion."""
        with self.lock:
            row = self.store.active()
            if not row or row["id"] != op:
                raise ValueError("No active operation to secure.")
            result = self.device(self.hardware.lock)
            if not result.ok:
                raise ValueError(result.message)
            self.store.record_lock_ack(op, self.operator)

    def cancel(self, op, reason):
        with self.lock:
            self.store.cancel(op, self.operator, reason or "Cancelled after access")
            result = self.device(self.hardware.lock)
            if not result.ok:
                raise ValueError("Reconciliation is required. " + result.message)

    def reconcile(self, op, count, reason, closed=False, remaining_ids=None):
        with self.lock:
            self.store.reconcile(op, count, self.operator, reason, closed=closed, remaining_ids=remaining_ids)
            return self.device(self.hardware.lock)
