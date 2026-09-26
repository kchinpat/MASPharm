"""Exercise real App workflow methods with dialogs and hardware callbacks controlled."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from pharm.app import App, saved_catalog_path
from pharm.catalog import Catalog
from pharm.hardware import Result, SerialHardware, Simulator
from pharm.store import Store
from test_inventory import PRODUCT


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App.__new__(App)
        self.app.store = Store(Path(self.temp.name) / "stock.sqlite3")
        self.app.store.add_user("admin", "test-password-123", "admin")
        self.app.operator, self.app.role, self.app.root = "admin", "admin", None
        self.app.hardware = Simulator()
        self.app.catalog = Catalog(Path(self.temp.name) / "absent.json")
        self.app.status_text = type("Status", (), {"set": lambda self, text: None})()
        self.app.home = lambda: None
        self.app.device = lambda action, done: done(action())
        self.dialogs = patch("pharm.app.messagebox")
        self.messages = self.dialogs.start()
        self.messages.askyesno.return_value = True
        op = self.app.store.begin("load", 1, 3, PRODUCT, "admin")
        self.app.store.access(op, "admin")
        self.app.store.finish(op, "admin", closed=True)

    def tearDown(self):
        self.dialogs.stop()
        self.temp.cleanup()

    def test_successful_dispense_through_ui(self):
        with patch("pharm.app.simpledialog.askinteger", return_value=2), \
             patch("pharm.app.simpledialog.askstring", return_value="0123456789"):
            self.app.dispense(1)
        self.assertEqual(1, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())
        self.assertIsNone(self.app.hardware.selected)

    def test_partial_scan_failure_stays_pending(self):
        with patch("pharm.app.simpledialog.askinteger", return_value=2), \
             patch("pharm.app.simpledialog.askstring", side_effect=["0123456789", "wrong"]):
            self.app.dispense(1)
        self.assertEqual("reconciliation", self.app.store.active()["state"])
        self.assertEqual(1, self.app.store.active()["verified"])
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])

    def test_cancelled_quantity_never_requests_hardware(self):
        with patch("pharm.app.simpledialog.askinteger", return_value=None):
            self.app.dispense(1)
        self.assertIsNone(self.app.store.active())
        self.assertIsNone(self.app.hardware.selected)

    def test_open_failure_is_durably_reconcilable(self):
        self.app.hardware.open = lambda number: Result(False, "No acknowledgement")
        with patch("pharm.app.simpledialog.askinteger", return_value=1):
            self.app.dispense(1)
        self.assertEqual("reconciliation", self.app.store.active()["state"])
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])

    def test_usb_handshake_timeout_does_not_block_inventory(self):
        uart = Mock(is_open=True)
        uart.write.return_value = 1
        uart.readline.return_value = b""
        self.app.hardware = SerialHardware("COM3", lambda: uart)
        completed = Mock()
        self.app.start_access("dispense", 1, 1, {}, completed)
        self.assertIsNone(self.app.store.active())
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])
        self.assertTrue(any(event["action"] == "access_not_sent" for event in self.app.store.audit()))
        self.assertEqual("Arduino connection not ready", self.messages.showerror.call_args.args[0])
        completed.assert_not_called()
        self.assertEqual([b"\x00"] * 3, [call.args[0] for call in uart.write.call_args_list])

    def test_unsent_load_does_not_save_product_or_quantity(self):
        self.app.hardware.open = lambda number: Result(False, "No firmware reply", action_attempted=False)
        self.app.start_access("load", 2, 5, PRODUCT, Mock())
        self.assertIsNone(self.app.store.active())
        self.assertEqual({}, self.app.store.compartments()[1]["product"])
        self.assertEqual(0, self.app.store.compartments()[1]["quantity"])

    def test_existing_reconciliation_cannot_be_cancelled_as_unsent(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.cancel(op, "admin", "Lost response")
        with self.assertRaises(ValueError):
            self.app.store.cancel(op, "admin", "No command sent", access_attempted=False)
        self.assertEqual("reconciliation", self.app.store.active()["state"])

    def test_verified_access_cannot_be_cancelled_as_unsent(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.verify_one(op, "admin")
        with self.assertRaises(ValueError):
            self.app.store.cancel(op, "admin", "No command sent", access_attempted=False)
        self.assertEqual(1, self.app.store.active()["verified"])

    def test_lock_failure_prevents_commit(self):
        self.app.hardware.lock = lambda: Result(False, "Lock failed")
        with patch("pharm.app.simpledialog.askinteger", return_value=1), \
             patch("pharm.app.simpledialog.askstring", return_value="0123456789"):
            self.app.dispense(1)
        self.assertEqual("reconciliation", self.app.store.active()["state"])
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])

    def test_unload_through_ui(self):
        self.app.unload(1)
        self.assertEqual(0, self.app.store.compartments()[0]["quantity"])

    def test_reconcile_through_ui(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.cancel(op, "admin", "Power loss")
        with patch("pharm.app.simpledialog.askinteger", return_value=2), \
             patch("pharm.app.simpledialog.askstring", return_value="Counted remaining bottles"):
            self.app.reconcile()
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())

    def test_valid_catalog_selection_persists_across_startup(self):
        path = Path(self.temp.name) / "packages.json"
        path.write_text(json.dumps([{"generic_name": "SYNTHETIC",
                                    "packaging": [{"package_ndc": "00123"}]}]))
        with patch("pharm.app.filedialog.askopenfilename", return_value=str(path)):
            self.app.choose_catalog()
        saved = saved_catalog_path(self.app.store.path.parent, Path("missing.json"))
        self.assertEqual(path.resolve(), saved)
        self.assertEqual("SYNTHETIC", Catalog(saved).lookup("00123")["generic_name"])

    def test_invalid_catalog_selection_keeps_current_catalog(self):
        previous = self.app.catalog
        path = Path(self.temp.name) / "invalid.json"
        path.write_text("{}")
        with patch("pharm.app.filedialog.askopenfilename", return_value=str(path)):
            self.app.choose_catalog()
        self.assertIs(previous, self.app.catalog)
        self.assertFalse((path.parent / "catalog-path.json").exists())

    def test_corrupt_catalog_preference_does_not_prevent_startup(self):
        path = Path(self.temp.name) / "catalog-path.json"
        default = Path("fallback.json")
        for content in ("broken", "null", "{}", '""'):
            path.write_text(content)
            self.assertEqual(default, saved_catalog_path(path.parent, default))


if __name__ == "__main__":
    unittest.main()
