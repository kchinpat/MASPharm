"""Real loading-screen controls using a temporary inventory and no hardware."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
import json
import time
from unittest.mock import patch

from pharm.app import App
from pharm.catalog import Catalog
from pharm.hardware import Simulator
from pharm.store import Store
from test_inventory import PRODUCT


class LoadingScreenTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Desktop Tcl/Tk is unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        self.app = App(self.root, Store(directory / "inventory.sqlite3"),
                       Catalog(directory / "absent.json"), Simulator())
        self.addCleanup(self.app.executor.shutdown, wait=True)
        self.messages = patch("pharm.app.dialogs").start()
        self.addCleanup(patch.stopall)

    def form(self):
        self.app.loading(1)
        self.root.update()
        form = self.app.load_form
        self.assertEqual("Look up", form["lookup"].cget("text"))
        return {"scan": form["scan"], **form["fields"]}, form["lookup"]

    def load_existing(self):
        store, actor = self.app.store, self.app.operator
        operation = store.begin("load", 1, 2, PRODUCT, actor)
        store.access(operation, actor)
        store.finish(operation, actor, closed=True)

    def test_missing_catalog_scan_populates_manual_identifier(self):
        entries, button = self.form()
        entries["scan"].insert(0, "00123-456")
        button.invoke()
        self.assertEqual("00123456", entries["ndc"].get())
        self.assertEqual("", entries["generic_name"].get())
        self.messages.showerror.assert_not_called()
        self.assertIn("manually", self.app.status_text.get())

    def test_topup_scan_preserves_existing_lot_expiration_and_unit(self):
        self.load_existing()
        entries, button = self.form()
        entries["scan"].insert(0, PRODUCT["ndc"])
        button.invoke()
        self.assertEqual(PRODUCT["lot"], entries["lot"].get())
        self.assertEqual(PRODUCT["expiry_date"], entries["expiry_date"].get())
        self.assertEqual(PRODUCT["unit"], entries["unit"].get())

    def test_different_scan_clears_previous_stock_identity(self):
        self.load_existing()
        entries, button = self.form()
        entries["scan"].insert(0, "9999999999")
        button.invoke()
        self.assertEqual("9999999999", entries["ndc"].get())
        for key in ("generic_name", "lot", "expiry_date", "unit"):
            self.assertEqual("", entries[key].get())
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])

    def gs1_catalog(self):
        path = Path(self.temp.name) / "packages.json"
        path.write_text(json.dumps([{"generic_name": PRODUCT["generic_name"],
                                    "packaging": [{"package_ndc": PRODUCT["ndc"]}],
                                    "openfda": {"upc": ["001234567895"]}}]))
        self.app.catalog = Catalog(path)

    def test_gs1_topup_retains_identity_but_uses_the_new_boxes_lot_and_expiry(self):
        self.gs1_catalog()
        self.load_existing()
        entries, button = self.form()
        entries["scan"].insert(0, "(01)00001234567895(21)NEW-BOX(17)981231(10)NEW-LOT")
        button.invoke()
        self.assertEqual("NEW-LOT", entries["lot"].get())
        self.assertEqual("2098-12-31", entries["expiry_date"].get())
        self.assertEqual(PRODUCT["unit"], entries["unit"].get())

    def test_real_loading_controls_commit_a_serialized_box_through_simulated_hardware(self):
        self.gs1_catalog()
        entries, button = self.form()
        entries["scan"].insert(0, "(01)00001234567895(21)TK-BOX(17)991231(10)TK-LOT")
        button.invoke()
        entries["unit"].insert(0, "box")
        self.messages.askyesno.return_value = True
        load_button = self.app.load_form["load"]
        self.assertEqual("Confirm and load", load_button.cget("text"))
        with patch("pharm.app.dialogs.askinteger", return_value=1):
            load_button.invoke()
        self.assertEqual(0, self.app.store.compartments()[0]["quantity"])
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and self.app.store.active():
            self.root.update()
            time.sleep(0.01)
        item = self.app.store.compartments()[0]
        self.assertEqual(1, item["quantity"])
        self.assertEqual("TK-BOX", item["items"][0]["serial"])

    def test_enter_key_cannot_change_fields_during_device_request(self):
        self.load_existing()
        entries, _ = self.form()
        previous = entries["ndc"].get()
        entries["scan"].insert(0, "9999999999")
        self.app.busy = True
        self.root.deiconify()
        self.root.update()
        entries["scan"].focus_force()
        self.root.update()
        entries["scan"].event_generate("<Return>")
        self.root.update()
        self.assertEqual(previous, entries["ndc"].get())
        self.app.busy = False
        entries["scan"].event_generate("<Return>")
        self.root.update()
        self.assertEqual("9999999999", entries["ndc"].get())
