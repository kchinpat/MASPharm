"""Cross-interface regressions for the combined package-tracking workflows."""
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from datetime import date, timedelta

from pharm.barcodes import read_scan, expiry_date
from pharm.catalog import Catalog
from pharm.hardware import Simulator, Result
from pharm.store import Store
from pharm.team_hardware import TeamSerialHardware
from pharm.web import create_app
from pharm.workflows import WorkflowService
from pharm.photos import fetch_photo, cached, OfficialRedirects
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


class CombinedTests(CombinedFixture):
    def test_gs1_maps_only_through_exact_catalog_aliases(self):
        self.assertEqual(PRODUCT["ndc"], self.catalog.lookup(barcode())["ndc"])
        self.assertTrue(self.catalog.matches(barcode(), PRODUCT["ndc"]))
        self.assertFalse(self.catalog.matches(barcode(), "123456789"))

    def test_scan_supplies_actual_lot_and_expiry(self):
        preview = self.service.preview(barcode())
        self.assertEqual("DEMO-LOT", preview["product"]["lot"])
        self.assertEqual("2099-12-31", preview["product"]["expiry_date"])
        self.assertEqual("BOX1", preview["scan"]["serial"])

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
        page = self.client.get("/").get_data(as_text=True)
        self.token = page.split('const token = "', 1)[1].split('"', 1)[0]

    def post(self, path, data):
        return self.client.post(path, json=data, headers={"X-Pharm-Token": self.token})

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

    def test_bad_types_and_invalid_drawers_never_change_stock(self):
        for data in ({"kind":"load","drawer":True,"count":1,"product":PRODUCT},
                     {"kind":"load","drawer":5,"count":1,"product":PRODUCT},
                     {"kind":"load","drawer":1,"count":True,"product":PRODUCT},
                     {"kind":"load","drawer":1,"count":1,"product":[]},
                     {"kind":"manual","drawer":1,"reason":[]},
                     {"kind":"manual","drawer":1,"reason":"", "unexpected":"x"}):
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


class TeamAdapterTests(unittest.TestCase):
    def uart(self, replies):
        uart = Mock(is_open=True)
        uart.write.return_value = 1
        uart.read.side_effect = replies
        return uart

    def test_adapter_is_lazy_and_requires_status_before_actuating(self):
        uart = self.uart([b"\x00",b"\x20",b"\x01"])
        factory = Mock(return_value=uart)
        adapter = TeamSerialHardware("COM9", factory)
        factory.assert_not_called()
        self.assertTrue(adapter.open(1).ok)
        self.assertEqual([b"\x30",b"\x20",b"\x01"], [c.args[0] for c in uart.write.call_args_list])

    def test_mas1_text_is_rejected_before_any_actuator_command(self):
        uart = self.uart([b"MA"])
        result = TeamSerialHardware("COM9", lambda:uart).open(1)
        self.assertFalse(result.ok)
        self.assertFalse(result.action_attempted)
        self.assertEqual([b"\x30"], [c.args[0] for c in uart.write.call_args_list])

    def test_lost_unlock_echo_is_never_retried(self):
        uart = self.uart([b"\x00",b"\x20",b""])
        result = TeamSerialHardware("COM9", lambda:uart).open(1)
        self.assertFalse(result.ok)
        self.assertTrue(result.action_attempted)
        self.assertEqual(1, [c.args[0] for c in uart.write.call_args_list].count(b"\x01"))

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

    def test_photo_cache_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            cached(".", "../private")

    def test_photo_redirects_cannot_leave_the_official_host(self):
        with self.assertRaises(ValueError):
            OfficialRedirects().redirect_request(None, None, 302, "", {}, "https://untrusted.example/photo.jpg")


if __name__ == "__main__":
    unittest.main()
