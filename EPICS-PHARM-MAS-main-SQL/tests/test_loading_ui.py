"""Real loading-screen controls using a temporary inventory and no hardware."""
from pathlib import Path
import tempfile
import threading
import tkinter as tk
from tkinter import ttk
import unittest
import json
import time
from unittest.mock import patch

from pharm.app import PROGRESS_SECONDS, App, plural
from pharm.catalog import Catalog, identifier
from pharm.hardware import Result, Simulator
from pharm.store import Store
from pharm.widgets import Progress
from test_inventory import PRODUCT

# A 1x1 GIF, which Tk shows without an image library.
GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00"
       b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")


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
        self.download = patch("pharm.app.fetch_photo", side_effect=ValueError("No photo in tests.")).start()
        self.addCleanup(patch.stopall)
        self.app = App(self.root, Store(directory / "inventory.sqlite3"),
                       Catalog(directory / "absent.json"), Simulator())
        self.addCleanup(self.app.executor.shutdown, wait=True)
        self.messages = patch("pharm.app.dialogs").start()

    def widgets(self):
        found, pending = [], [self.app.content]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            found.append(widget)
        return found

    def texts(self):
        return [w.cget("text") for w in self.widgets() if isinstance(w, (tk.Label, ttk.Button))]

    def pump_until(self, condition):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not condition():
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(condition())

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

    def test_drug_barcode_fills_medication_and_unit_type_then_loads(self):
        path = Path(self.temp.name) / "described.json"
        path.write_text(json.dumps([{"generic_name": PRODUCT["generic_name"],
                                     "packaging": [{"package_ndc": PRODUCT["ndc"], "description": "1 TUBE in 1 CARTON (01234-5678-9)"}]}]))
        self.app.catalog = Catalog(path)
        entries, button = self.form()
        entries["scan"].insert(0, "(01)00301234567896(21)RX-BOX(17)991231(10)RX-LOT")
        button.invoke()
        self.assertEqual((PRODUCT["generic_name"], "carton", PRODUCT["ndc"]),
                         (entries["generic_name"].get(), entries["unit"].get(), entries["ndc"].get()))
        self.messages.askyesno.return_value = True
        with patch("pharm.app.dialogs.askinteger", return_value=1):
            self.app.load_form["load"].invoke()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and self.app.store.active():
            self.root.update()
            time.sleep(0.01)
        item = self.app.store.compartments()[0]
        self.assertEqual((1, "carton"), (item["quantity"], item["product"]["unit"]))

    def test_missing_generic_name_is_reported_before_asking_for_a_quantity(self):
        entries, button = self.form()
        entries["scan"].insert(0, "(01)00001234567895(21)NO-NAME(17)991231(10)LOT-1")
        button.invoke()
        entries["unit"].insert(0, "box")
        events = len(self.app.store.audit())
        self.app.load_form["load"].invoke()
        self.messages.showerror.assert_called_once()
        self.assertIn("Generic name is required", self.messages.showerror.call_args.args[1])
        self.messages.askinteger.assert_not_called()
        self.messages.askstring.assert_not_called()
        self.assertIsNone(self.app.store.active())
        self.assertEqual(events, len(self.app.store.audit()))

    def test_bad_box_is_reported_when_scanned_not_after_every_box(self):
        self.gs1_catalog()
        entries, button = self.form()
        entries["scan"].insert(0, "(01)00001234567895(21)BOX-1(17)991231(10)LOT-1")
        button.invoke()
        entries["unit"].insert(0, "box")
        self.messages.askinteger.return_value = 3
        self.messages.askstring.side_effect = ["(01)00001234567895(21)BOX-1(17)991231(10)LOT-1",
                                               "(01)00001234567895(21)BOX-3(17)991231(10)LOT-1"]
        self.app.load_form["load"].invoke()
        self.assertEqual(1, self.messages.askstring.call_count)
        self.assertIn("already recorded", self.messages.showerror.call_args.args[1])
        self.assertIsNone(self.app.store.active())

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


    def test_progress_screen_covers_the_form_until_the_drawer_unlocks(self):
        self.form()
        release, results = threading.Event(), []
        started = time.monotonic()
        self.app.device(lambda: release.wait(5) and Result(True, "Opened."), results.append, "Unlocking drawer 1", "open")
        self.root.update()
        covers = [w for w in self.app.panel.winfo_children() if isinstance(w, Progress)]
        self.assertEqual(1, len(covers))
        self.assertIn("disabled", self.app.scan.state())
        self.assertRegex(covers[0].left.get(), r"^About \d+ seconds? left$")
        release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not results:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(results[0].ok)
        self.assertGreaterEqual(time.monotonic() - started, PROGRESS_SECONDS)
        self.assertFalse(any(isinstance(w, Progress) for w in self.app.panel.winfo_children()))
        self.assertNotIn("disabled", self.app.scan.state())
        self.assertIn("open", self.app.estimates)

    def test_missing_label_photo_downloads_in_the_background_and_appears(self):
        release = threading.Event()

        def download(directory, code):
            release.wait(5)
            path = Path(directory) / (identifier(code) + ".gif")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(GIF)
            return path
        self.download.side_effect = download
        self.load_existing()
        self.app.home()
        self.root.update()
        self.assertIn("Downloading the label photo...", self.texts())
        self.assertFalse(self.app.busy)  # dispensing and loading never wait on it
        self.assertNotIn("disabled", self.app.scan.state())
        release.set()
        self.pump_until(lambda: any(isinstance(w, tk.Label) and w.cget("image") for w in self.widgets()))
        self.assertNotIn("Downloading the label photo...", self.texts())
        self.download.assert_called_once()

    def test_failed_label_photo_is_not_retried_until_asked(self):
        self.load_existing()
        self.app.home()
        self.pump_until(lambda: "No label photo available" in self.texts())
        self.app.home()
        self.root.update()
        self.assertEqual(1, self.download.call_count)
        retry = next(w for w in self.widgets() if isinstance(w, ttk.Button) and w.cget("text") == "Try again")
        retry.invoke()
        self.pump_until(lambda: self.download.call_count == 2 and "No label photo available" in self.texts())

    def test_package_lookup_starts_its_label_photo_download(self):
        entries, button = self.form()
        entries["scan"].insert(0, PRODUCT["ndc"])
        button.invoke()
        self.pump_until(lambda: self.download.call_count == 1)
        self.assertEqual(identifier(PRODUCT["ndc"]), identifier(self.download.call_args.args[1]))


class PluralTests(unittest.TestCase):
    def test_catalog_unit_types_read_naturally(self):
        for unit, expected in (("bottle", "bottles"), ("box", "boxes"), ("blister pack", "blister packs"), ("mL", "mL")):
            with self.subTest(unit=unit):
                self.assertEqual(expected, plural(unit, 2))
                self.assertEqual(unit, plural(unit, 1))
