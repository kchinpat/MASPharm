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

from pharm.app import PROGRESS_SECONDS, App, capitalized, plural, saved_palette, saved_ui, save_palette, startup_palette
from pharm.catalog import Catalog, identifier
from pharm.hardware import Result, Simulator
from pharm.store import Store
from pharm.widgets import Progress
from test_inventory import PRODUCT
from UI import theme as T

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

    def scan_top_bar(self, code):
        self.app.scan.insert(0, code)
        self.app.find()
        self.root.update()

    def test_top_bar_scan_of_a_new_package_fills_the_selected_drawers_load_form(self):
        self.gs1_catalog()
        self.app.select(3)
        self.scan_top_bar("(01)00001234567895(21)TOP-BOX(17)991231(10)TOP-LOT")
        self.assertEqual(("load", 3), (self.app.view, self.app.selected))
        fields = self.app.load_form["fields"]
        self.assertEqual((PRODUCT["generic_name"], PRODUCT["ndc"], "TOP-LOT", "2099-12-31"),
                         tuple(fields[k].get() for k in ("generic_name", "ndc", "lot", "expiry_date")))
        self.assertIsNone(self.app.store.active())  # nothing unlocks until the details are confirmed
        fields["unit"].insert(0, "box")
        self.messages.askyesno.return_value = True
        with patch("pharm.app.dialogs.askinteger", return_value=1):
            self.app.load_form["load"].invoke()
        self.pump_until(lambda: self.app.store.compartments()[2]["quantity"] == 1)
        self.assertEqual("TOP-BOX", self.app.store.compartments()[2]["items"][0]["serial"])

    def test_top_bar_scan_of_a_new_package_leaves_a_stocked_drawer_alone(self):
        self.load_existing()
        self.app.home()
        self.scan_top_bar("9999999999")
        self.assertEqual("drawer", self.app.view)
        self.assertIn("select an empty drawer", self.app.status_text.get())
        self.assertIn(PRODUCT["generic_name"], self.app.status_text.get())

    def test_top_bar_scan_of_a_stocked_package_still_dispenses_from_its_drawer(self):
        self.load_existing()
        self.app.select(3)
        self.messages.askinteger.return_value = None
        self.scan_top_bar(PRODUCT["ndc"])
        self.assertEqual(("drawer", 1), (self.app.view, self.app.selected))
        self.assertEqual("Dispense", self.messages.askinteger.call_args.args[0])

    def test_top_bar_scan_that_is_not_a_barcode_opens_nothing(self):
        self.scan_top_bar("not a barcode")
        self.assertEqual("drawer", self.app.view)
        self.assertEqual("Unsupported package barcode format.", self.app.status_text.get())
        self.messages.showerror.assert_not_called()

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


class UiTwoTests(unittest.TestCase):
    """UI two, the Console layout and the default, driven through the real window."""

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Desktop Tcl/Tk is unavailable: {exc}")
        self.addCleanup(T.use_palette, "light")
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        patch("pharm.app.fetch_photo", side_effect=ValueError("No photo in tests.")).start()
        self.addCleanup(patch.stopall)
        path = directory / "catalog.json"
        path.write_text(json.dumps([{"generic_name": PRODUCT["generic_name"], "active_ingredients": [{"strength": ".5 mg/1"}],
                                     "packaging": [{"package_ndc": PRODUCT["ndc"]}]}]))
        store = Store(directory / "inventory.sqlite3")
        T.use_palette(startup_palette(directory))  # as main() starts the window
        self.app = App(self.root, store, Catalog(path), Simulator())
        self.addCleanup(self.app.executor.shutdown, wait=True)
        self.messages = patch("pharm.app.dialogs").start()
        operation = store.begin("load", 2, 2, PRODUCT, self.app.operator)
        store.access(operation, self.app.operator)
        store.finish(operation, self.app.operator, closed=True)
        self.app.home()
        self.root.update()

    def switch(self):
        self.app.toggle_ui()
        self.root.update()

    def texts(self, parent):
        found, pending = [], [parent]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            if isinstance(widget, (tk.Label, ttk.Button)):
                found.append(widget.cget("text"))
        return found

    def menu(self):
        return [entry[0] for entry in self.app.main_menu() if entry]

    def test_ui_two_is_the_default_and_the_switch_works_both_ways_and_is_remembered(self):
        directory = self.app.store.path.parent
        self.assertEqual("two", saved_ui(directory))
        self.assertEqual("console", T.PALETTE)
        self.assertIn("Switch to legacy UI", self.menu())
        self.assertIn("Light theme", self.menu())
        self.switch()
        self.assertFalse(T.console())
        self.assertEqual("one", saved_ui(directory))
        self.assertEqual("light", startup_palette(directory))
        self.assertIn("Switch to new UI", self.menu())
        self.assertIn("Dark theme", self.menu())
        self.assertEqual("#ffffff", T.SURFACE)
        self.switch()
        self.assertEqual("console", T.PALETTE)
        self.assertEqual("two", saved_ui(directory))

    def test_the_menu_opens_in_ui_two_and_its_item_switches_to_the_legacy_ui(self):
        with patch("tkinter.Menu.tk_popup"), patch("tkinter.Menu.add_command") as add:
            self.app.popup(self.app.scan, self.app.main_menu())
        labels = [call.kwargs["label"] for call in add.call_args_list]
        self.assertEqual(["Light theme", "Switch to legacy UI"], labels[-2:])
        add.call_args_list[-1].kwargs["command"]()
        self.assertFalse(T.console())

    def test_each_ui_returns_to_its_own_saved_theme(self):
        directory = self.app.store.path.parent
        save_palette(directory, "dark")
        self.switch()
        self.assertEqual("dark", T.PALETTE)
        self.switch()
        self.assertEqual("console", T.PALETTE)
        self.assertEqual("dark", saved_palette(directory))

    def test_ui_two_has_a_light_theme_of_its_own_that_is_remembered(self):
        directory = self.app.store.path.parent
        self.app.toggle_theme()
        self.root.update()
        self.assertEqual("console_light", T.PALETTE)
        self.assertTrue(T.console())
        self.assertIn("Dark theme", self.menu())
        self.assertEqual(("console_light", "light"), (saved_palette(directory, two=True), saved_palette(directory)))
        self.assertEqual("console_light", startup_palette(directory))
        # The window is redrawn in the light palette, and its styles are not the legacy UI's.
        self.assertEqual(("#eef1f3", "#ffffff"), (self.root.cget("bg"), self.app.panel.cget("bg")))
        self.assertIn(T.IDLE, [w.cget("bg") for w in self.app.cabinet.winfo_children() if w is not self.app.panel_box])
        self.assertEqual(3, self.columns().count("Empty"))
        self.assertNotEqual("Primary.TButton", self.app.theme.button_style("Primary"))
        self.switch()
        self.assertEqual("light", T.PALETTE)
        self.switch()
        self.assertEqual("console_light", T.PALETTE)
        self.app.toggle_theme()
        self.assertEqual(("console", "console"), (T.PALETTE, saved_palette(directory, two=True)))

    def test_home_shows_every_drawer_with_its_strength_and_no_panel(self):
        self.assertEqual(0, self.app.focus_drawer(None))
        self.assertFalse(self.app.panel_box.winfo_ismapped())
        shown = self.columns()
        self.assertEqual(3, shown.count("Empty"))
        self.assertIn(capitalized(PRODUCT["generic_name"]), shown)
        self.assertIn(f"0.5 mg  ·  {PRODUCT['labeler_name']}" if PRODUCT.get("labeler_name") else "0.5 mg", shown)
        self.assertEqual(1, shown.count("DISPENSE"))
        self.assertEqual(3, len([t for t in shown if t.startswith("LOAD DRAWER")]))

    def columns(self):
        """The text on the drawers, without the panel that is out of view."""
        return [text for widget in self.app.cabinet.winfo_children() if widget is not self.app.panel_box
                for text in self.texts(widget)]

    def test_the_drawer_being_worked_on_widens_and_the_others_hold(self):
        self.app.loading(2)
        self.root.update()
        self.assertEqual(2, self.app.focus_drawer(None))
        self.assertEqual(1, self.app.panel_box.grid_info()["column"])
        self.assertEqual(3, self.columns().count("HELD"))
        self.assertEqual(3, len([w for w in self.app.cabinet.winfo_children() if w is not self.app.panel_box]))

    def test_a_step_about_no_one_drawer_sits_after_them_all(self):
        self.app.busy, self.app.context = True, ""
        self.assertEqual(5, self.app.focus_drawer(None))
        self.app.busy = False

    def test_more_opens_the_drawer_and_close_returns_to_the_columns(self):
        self.app.show_detail(2)
        self.root.update()
        self.assertEqual(2, self.app.focus_drawer(None))
        self.assertIn("LOAD MORE", self.texts(self.app.content))
        self.app.close_detail()
        self.root.update()
        self.assertEqual(0, self.app.focus_drawer(None))

    def test_an_outstanding_count_holds_every_other_drawer(self):
        operation = self.app.store.begin("dispense", 2, 1, {}, self.app.operator)
        self.app.store.access(operation, self.app.operator)
        self.app.store.cancel(operation, self.app.operator, "Interrupted")
        self.app.home()
        self.assertEqual(2, self.app.focus_drawer(self.app.store.active()))
        self.assertEqual(3, self.columns().count("HELD"))
        self.assertEqual("DRAWER 2 NEEDS A COUNT", self.app.placeholder.cget("text"))

    def test_recent_activity_reads_as_plain_sentences(self):
        shown = self.texts(self.app.log_rows)
        self.assertIn(f"Loaded 2 bottles of {PRODUCT['generic_name']} into drawer 2", shown)
        self.assertEqual(2, len(shown))  # a time and one line; the session start is not shown
        self.assertFalse(any("local-workstation" in text or "operator" in text for text in shown))

    def test_load_form_shows_strength_and_serial_but_saves_neither(self):
        self.app.loading(1)
        self.root.update()
        form = self.app.load_form
        self.assertNotIn("strength", form["fields"])
        self.assertNotIn("serial", form["fields"])
        form["scan"].insert(0, PRODUCT["ndc"])
        form["lookup"].invoke()
        self.assertEqual(PRODUCT["ndc"], form["fields"]["ndc"].get())
        self.assertIn("0.5 mg", self.entries(self.app.content))

    def entries(self, parent):
        found, pending = [], [parent]
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            if isinstance(widget, ttk.Entry):
                found.append(widget.get())
        return found

    def test_a_new_package_scanned_on_home_goes_to_the_first_empty_drawer(self):
        self.app.selected = 2
        self.app.load_scan("9999999999")
        self.assertEqual(("load", 1), (self.app.view, self.app.selected))

    def test_dispensing_lists_each_scan_and_offers_reopen(self):
        self.messages.askinteger.return_value = 2
        self.messages.askstring.side_effect = [PRODUCT["ndc"], None]
        self.messages.askyesno.return_value = True
        self.app.dispense(2)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and self.messages.askstring.call_count < 2:
            self.root.update()
            time.sleep(0.01)
        first, second = self.messages.askstring.call_args_list
        self.assertTrue(first.kwargs["reopen"])
        self.assertEqual("Scan now", first.kwargs["steps"][0][1])
        self.assertEqual(("Verified", "Scan now"), (second.kwargs["steps"][0][1], second.kwargs["steps"][1][1]))
        self.assertEqual(f"Scan {PRODUCT['unit']} 2 of 2", second.args[1])

    def test_a_long_dispense_only_lists_the_units_around_the_current_one(self):
        rows = self.app.dispense_steps([("A", "t")] * 5, 20)
        self.assertEqual([(5, "Verified"), (6, "Scan now"), (7, "Waiting")], [row[:2] for row in rows])
        self.assertEqual(2, len(self.app.dispense_steps([], 2)))


class PluralTests(unittest.TestCase):
    def test_a_catalog_name_keeps_its_spelling_with_a_capital_to_start(self):
        self.assertEqual("Warfarin Sodium", capitalized("Warfarin Sodium"))
        self.assertEqual("Alprazolam", capitalized("alprazolam"))
        self.assertEqual("", capitalized(""))

    def test_catalog_unit_types_read_naturally(self):
        for unit, expected in (("bottle", "bottles"), ("box", "boxes"), ("blister pack", "blister packs"), ("mL", "mL")):
            with self.subTest(unit=unit):
                self.assertEqual(expected, plural(unit, 2))
                self.assertEqual(unit, plural(unit, 1))
