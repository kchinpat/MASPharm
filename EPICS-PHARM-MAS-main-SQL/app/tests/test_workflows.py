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
        self.app.device = lambda action, done, *_: done(action())
        self.dialogs = patch("pharm.app.dialogs")
        self.messages = self.dialogs.start()
        self.messages.askyesno.return_value = True
        op = self.app.store.begin("load", 1, 3, PRODUCT, "admin")
        self.app.store.access(op, "admin")
        self.app.store.finish(op, "admin", closed=True)

    def tearDown(self):
        self.dialogs.stop()
        self.temp.cleanup()

    def test_successful_dispense_through_ui(self):
        with patch("pharm.app.dialogs.askinteger", return_value=2), \
             patch("pharm.app.dialogs.askstring", return_value="0123456789"):
            self.app.dispense(1)
        self.assertEqual(1, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())
        self.assertIsNone(self.app.hardware.selected)

    def test_cancelled_scan_after_partial_verification_stays_pending(self):
        with patch("pharm.app.dialogs.askinteger", return_value=2), \
             patch("pharm.app.dialogs.askstring", side_effect=["0123456789", "wrong", None]):
            self.app.dispense(1)
        self.assertEqual("reconciliation", self.app.store.active()["state"])
        self.assertEqual(1, self.app.store.active()["verified"])
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])

    def test_rejected_scan_is_scanned_again_without_reconciliation(self):
        scans = ["0123456789", "01234", "]d2garbled", "0123456789"]
        with patch("pharm.app.dialogs.askinteger", return_value=2), \
             patch("pharm.app.dialogs.askstring", side_effect=scans) as ask:
            self.app.dispense(1)
        self.assertIsNone(self.app.store.active())
        self.assertEqual(1, self.app.store.compartments()[0]["quantity"])
        errors = [call.kwargs["error"] for call in ask.call_args_list]
        self.assertEqual("", errors[0])
        self.assertIn("different package", errors[2])
        self.assertIn("Scan the box again", errors[3])
        self.assertIn("Scan item 2 of 2", ask.call_args_list[3].args[1])

    def test_cancelled_quantity_never_requests_hardware(self):
        with patch("pharm.app.dialogs.askinteger", return_value=None):
            self.app.dispense(1)
        self.assertIsNone(self.app.store.active())
        self.assertIsNone(self.app.hardware.selected)

    def test_open_failure_is_durably_reconcilable(self):
        self.app.hardware.open = lambda number: Result(False, "No acknowledgement")
        with patch("pharm.app.dialogs.askinteger", return_value=1):
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

    def test_lock_failure_does_not_prevent_commit(self):
        self.app.hardware.lock = lambda: Result(False, "Lock failed")
        with patch("pharm.app.dialogs.askinteger", return_value=1), \
             patch("pharm.app.dialogs.askstring", return_value="0123456789"):
            self.app.dispense(1)
        self.assertIsNone(self.app.store.active())
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])
        self.messages.askyesno.assert_not_called()
        self.assertEqual("Inventory saved", self.messages.showwarning.call_args.args[0])

    def test_reconcile_saves_without_lock_acknowledgement_or_security_prompt(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.cancel(op, "admin", "Power loss")
        self.app.hardware.lock = lambda: Result(False, "Disconnected")
        with patch("pharm.app.dialogs.askinteger", return_value=2), \
             patch("pharm.app.dialogs.askstring", return_value="Counted remaining bottles"):
            self.app.reconcile()
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())
        self.messages.askyesno.assert_not_called()

    def test_unload_through_ui(self):
        self.app.unload(1)
        self.assertEqual(0, self.app.store.compartments()[0]["quantity"])
        self.assertEqual(["Unload", "Drawer 1 is open"], [call.args[0] for call in self.messages.askyesno.call_args_list])

    def test_cancelling_an_open_drawer_needs_a_count(self):
        self.messages.askyesno.side_effect = [True, False]
        self.app.unload(1)
        self.assertEqual("reconciliation", self.app.store.active()["state"])
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])

    def test_empty_scan_reopens_without_asking(self):
        opened = []
        open_drawer = self.app.hardware.open
        self.app.hardware.open = lambda number: (opened.append(number), open_drawer(number))[1]
        with patch("pharm.app.dialogs.askinteger", return_value=1), \
             patch("pharm.app.dialogs.askstring", side_effect=["", "0123456789"]):
            self.app.dispense(1)
        self.assertEqual([1, 1], opened)
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])
        self.messages.askyesno.assert_not_called()

    def test_reconcile_through_ui(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.cancel(op, "admin", "Power loss")
        with patch("pharm.app.dialogs.askinteger", return_value=2), \
             patch("pharm.app.dialogs.askstring", return_value="Counted remaining bottles"):
            self.app.reconcile()
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())

    def test_unlock_without_reason_saves_count_without_extra_prompts(self):
        self.messages.askinteger.side_effect = [1, 6]
        self.messages.askstring.return_value = ""
        self.app.manual()
        self.assertEqual(6, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())
        self.assertIsNone(self.app.hardware.selected)
        self.messages.askstring.assert_called_once()
        self.assertIn("Optional", self.messages.askstring.call_args.args[1])
        self.messages.askyesno.assert_not_called()
        self.messages.showwarning.assert_not_called()

    def test_cancelling_unlock_reason_does_not_open_drawer(self):
        self.messages.askinteger.return_value = 1
        self.messages.askstring.return_value = None
        self.app.manual()
        self.assertIsNone(self.app.store.active())
        self.assertIsNone(self.app.hardware.selected)

    def test_cancelling_manual_count_keeps_operation_available(self):
        self.messages.askinteger.side_effect = [1, None]
        self.messages.askstring.return_value = ""
        self.app.manual()
        self.assertEqual("manual", self.app.store.active()["kind"])
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])

    def test_interrupted_verified_dispense_finishes_without_count(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.verify_one(op, "admin")
        with patch("pharm.app.dialogs.askinteger") as count:
            self.app.reconcile()
        count.assert_not_called()
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())
        self.assertEqual(["Finish dispense"], [call.args[0] for call in self.messages.askyesno.call_args_list])

    def test_declining_finish_falls_back_to_count(self):
        op = self.app.store.begin("dispense", 1, 1, {}, "admin")
        self.app.store.access(op, "admin")
        self.app.store.verify_one(op, "admin")
        self.messages.askyesno.side_effect = [False]
        with patch("pharm.app.dialogs.askinteger", return_value=3), \
             patch("pharm.app.dialogs.askstring", return_value="Nothing was removed"):
            self.app.reconcile()
        self.assertEqual(3, self.app.store.compartments()[0]["quantity"])
        self.assertIsNone(self.app.store.active())

    def test_stock_saved_before_unit_rule_still_dispenses(self):
        legacy = json.dumps({**PRODUCT, "unit": "1"})
        with self.app.store.connect() as db:
            db.execute("UPDATE stock_items SET product=?", (legacy,))
            db.execute("UPDATE compartments SET product=? WHERE id=1", (legacy,))
        with patch("pharm.app.dialogs.askinteger", return_value=1), \
             patch("pharm.app.dialogs.askstring", return_value="0123456789"):
            self.app.dispense(1)
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
