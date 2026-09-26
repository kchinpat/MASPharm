"""Real loading-screen controls using a temporary inventory and no hardware."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
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
        self.messages = patch("pharm.app.messagebox").start()
        self.addCleanup(patch.stopall)

    def form(self):
        self.app.loading(1)
        self.root.update()
        widgets = self.app.content.winfo_children()
        entries = {int(w.grid_info()["row"]): w for w in widgets if isinstance(w, ttk.Entry)}
        button = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget("text") == "Use scan / look up")
        return entries, button

    def load_existing(self):
        store, actor = self.app.store, self.app.operator
        operation = store.begin("load", 1, 2, PRODUCT, actor)
        store.access(operation, actor)
        store.finish(operation, actor, closed=True)

    def test_missing_catalog_scan_populates_manual_identifier(self):
        entries, button = self.form()
        entries[1].insert(0, "00123-456")
        button.invoke()
        self.assertEqual("00123456", entries[4].get())
        self.assertEqual("", entries[3].get())
        self.messages.showerror.assert_not_called()
        self.assertIn("manually", self.app.status_text.get())

    def test_topup_scan_preserves_existing_lot_expiration_and_unit(self):
        self.load_existing()
        entries, button = self.form()
        entries[1].insert(0, PRODUCT["ndc"])
        button.invoke()
        self.assertEqual(PRODUCT["lot"], entries[5].get())
        self.assertEqual(PRODUCT["expiry_date"], entries[6].get())
        self.assertEqual(PRODUCT["unit"], entries[7].get())

    def test_different_scan_clears_previous_stock_identity(self):
        self.load_existing()
        entries, button = self.form()
        entries[1].insert(0, "9999999999")
        button.invoke()
        self.assertEqual("9999999999", entries[4].get())
        for row in (3, 5, 6, 7):
            self.assertEqual("", entries[row].get())
        self.assertEqual(2, self.app.store.compartments()[0]["quantity"])

    def test_enter_key_cannot_change_fields_during_device_request(self):
        self.load_existing()
        entries, _ = self.form()
        previous = entries[4].get()
        entries[1].insert(0, "9999999999")
        self.app.busy = True
        self.root.deiconify()
        self.root.update()
        entries[1].focus_force()
        self.root.update()
        entries[1].event_generate("<Return>")
        self.root.update()
        self.assertEqual(previous, entries[4].get())
        self.app.busy = False
        entries[1].event_generate("<Return>")
        self.root.update()
        self.assertEqual("9999999999", entries[4].get())
