"""Dependency-free Tkinter UI. All hardware I/O runs outside the UI thread.

The window mirrors the hardware: the four drawer fronts stacked on the left,
and one work panel on the right. Selecting a drawer shows what is in it and
what you can do; workflows then run there one guided step at a time.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # UI/theme.py lives beside this package

from UI import theme as T  # noqa: E402
from . import dialogs  # noqa: E402
from .catalog import Catalog  # noqa: E402
from .hardware import HttpHardware, Result, Simulator, SerialHardware, usb_ports  # noqa: E402
from .store import Store  # noqa: E402
from .barcodes import read_scan  # noqa: E402
from .catalog import identifier  # noqa: E402
from .team_hardware import TeamSerialHardware  # noqa: E402
from .photos import cached, fetch_photo  # noqa: E402
from .widgets import ScrollFrame, Splash, divider, label, set_window_icon  # noqa: E402

# key, label, columns spanned, optional (hidden under "More details")
FIELDS = (
    ("generic_name", "Medication", 2, False),
    ("ndc", "Package ID", 1, False),
    ("lot", "Lot", 1, False),
    ("expiry_date", "Expiration date (YYYY-MM-DD)", 1, False),
    ("unit", "Unit counted (bottle, box, tablet)", 1, False),
    ("description", "Package description", 2, True),
    ("brand_name", "Brand", 1, True),
    ("labeler_name", "Labeler", 1, True),
)


def plural(unit, count):
    """'bottle' -> 'bottles'; leaves abbreviations such as 'mL' alone."""
    unit = (unit or "").strip()
    if count == 1 or not unit.isalpha() or not unit.islower() or unit.endswith("s"):
        return unit
    return unit + ("es" if unit.endswith(("x", "ch", "sh")) else "s")


def expiry_days(expiry):
    return (date.fromisoformat(expiry) - date.today()).days


def expiry_note(expiry):
    """Short expiration wording and whether it needs attention (31-day window)."""
    days = expiry_days(expiry)
    if days < 0:
        return "Expired", True
    if days == 0:
        return "Expires today", True
    if days <= 31:
        return f"Expires in {days} day{'' if days == 1 else 's'}", True
    return f"Expires {expiry}", False


class App:
    def __init__(self, root, store, catalog, hardware):
        self.root, self.store, self.catalog, self.hardware = root, store, catalog, hardware
        self.operator = None
        self.role = None
        self.busy = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.theme = T.apply_theme(root)
        self.px = self.theme.px
        self.photos = []
        self.load_form = None
        self.view = None
        self.selected = 1
        self.prompt = None
        self.context = ""
        root.title("Pharmacy Drawer")
        if not getattr(root, "pharm_sized", False):
            size_window(root)
        root.minsize(self.px(900), self.px(600))
        root.bind("<Escape>", lambda _: root.attributes("-fullscreen", False))
        root.bind("<F11>", lambda _: root.attributes("-fullscreen", not root.attributes("-fullscreen")))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error
        self.status_text = tk.StringVar(value="Ready")
        self.status_at = 0.0
        self.status_job = None
        self.expiry_notice = None
        self.chrome()
        root.pharm_prompt_host = self
        self.status_text.trace_add("write", lambda *_: self.notify(fresh=True))
        self.operator = self.store.start_local_session()
        self.role = "admin"
        self.home()

    def callback_error(self, kind, value, traceback):
        logging.error("UI callback failed", exc_info=(kind, value, traceback))
        dialogs.showerror("Action failed", f"{value}\nAny unfinished access remains available for reconciliation.", parent=self.root)

    # -- Shell ----------------------------------------------------------------

    def chrome(self):
        px, theme, root = self.px, self.theme, self.root
        root.configure(bg=T.SHELL)
        bar = tk.Frame(root, bg=T.HEADER, padx=px(20), pady=px(14))
        bar.pack(fill="x")
        tk.Label(bar, image=theme.logo(px(34), T.HEADER, *T.LOGO), bg=T.HEADER).pack(side="left")
        label(bar, "Pharmacy Drawer", "heading", T.HEADER_TEXT, T.HEADER).pack(side="left", padx=(px(12), px(28)))
        menu = self.button(bar, "Menu", lambda: self.popup(menu, self.main_menu()), "Header", T.HEADER)
        menu.pack(side="right")
        simulated = isinstance(self.hardware, Simulator)
        tk.Label(bar, text="Simulation" if simulated else self.hardware.mode, font=theme.font("small"),
                 fg=T.HEADER_WARNING if simulated else T.HEADER_MUTED, bg=T.HEADER).pack(side="right", padx=(px(20), px(16)))
        self.scan = ttk.Entry(bar, style=theme.header_entry_style(), font=theme.font("scan"))
        self.scan.pack(side="left", fill="x", expand=True)
        self.placeholder = label(self.scan, "Scan a package to dispense", "body", T.HEADER_FIELD["placeholder"],
                                 T.HEADER_FIELD["fill"])
        self.placeholder.place(x=px(16), rely=0.5, anchor="w")
        self.placeholder.bind("<Button-1>", lambda _: self.scan.focus_set())
        self.scan.bind("<KeyRelease>", lambda _: self.update_placeholder())
        self.scan.bind("<FocusIn>", lambda _: self.update_placeholder())
        self.scan.bind("<FocusOut>", lambda _: self.update_placeholder())
        self.scan.bind("<Return>", self.find)

        body = tk.Frame(root, bg=T.SHELL)
        # A header band the color of the shell needs no gap below it.
        body.pack(fill="both", expand=True, padx=px(20), pady=(px(4) if T.HEADER == T.SHELL else px(20), px(20)))
        self.frames = (bar, body)
        body.columnconfigure(0, minsize=px(390))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self.cabinet = tk.Frame(body, bg=T.SHELL)
        self.cabinet.grid(row=0, column=0, sticky="nsew", padx=(0, px(20)))
        panel = ttk.Frame(body, style=theme.panel_style(), padding=px(6))
        panel.grid(row=0, column=1, sticky="nsew")
        self.panel = tk.Frame(panel, bg=T.SURFACE)
        self.panel.pack(fill="both", expand=True)
        self.scroll = ScrollFrame(self.panel, T.SURFACE)
        self.scroll.pack(fill="both", expand=True)
        self.content = self.scroll.body
        # Results appear briefly along the bottom of the work panel.
        self.status_bar = label(self.panel, font="strong", fg=T.ACCENT_DARK, bg=T.ACCENT_SOFT,
                                textvariable=self.status_text, padx=px(44), pady=px(12), wraplength=px(640))

    def update_placeholder(self):
        if self.scan.get():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=self.px(16), rely=0.5, anchor="w")

    def main_menu(self):
        return (("Unlock a drawer...", self.manual),
                ("Device status", lambda: self.device(self.hardware.status, lambda r: None)),
                None,
                ("Choose catalog...", self.choose_catalog),
                ("Export audit...", self.export_audit),
                ("Backup...", self.backup),
                None,
                ("Light theme" if T.PALETTE == "dark" else "Dark theme", self.toggle_theme))

    def toggle_theme(self):
        """Switch between the light and dark shell, remember it, and redraw."""
        palette = "light" if T.PALETTE == "dark" else "dark"
        T.use_palette(palette)
        try:
            save_palette(self.store.path.parent, palette)
        except OSError as exc:
            logging.warning("Could not save the theme choice: %s", exc)
        if self.status_job:
            self.root.after_cancel(self.status_job)
            self.status_job = None
        for frame in self.frames:
            frame.destroy()
        self.chrome()
        self.home()

    def popup(self, anchor, entries):
        """Show a dropdown of (label, command[, enabled]) under `anchor`."""
        if self.prompt:
            return
        menu = tk.Menu(self.root, tearoff=0, font=self.theme.font("body"))
        for entry in entries:
            if entry is None:
                menu.add_separator()
                continue
            text, command, *enabled = entry
            menu.add_command(label=text, command=lambda c=command: None if self.busy or self.prompt else c(),
                             state="normal" if not enabled or enabled[0] else "disabled")
        menu.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height())

    def notify(self, fresh=False):
        if fresh:
            self.status_at = time.monotonic()
        text = self.status_text.get()
        if self.view != "drawer" or not text or text == "Ready" or time.monotonic() - self.status_at > 2:
            self.status_bar.pack_forget()
            return
        self.status_bar.pack(side="bottom", fill="x", before=self.scroll)
        if self.status_job:
            self.root.after_cancel(self.status_job)
        self.status_job = None if self.busy else self.root.after(6000, self.status_bar.pack_forget)

    def hint(self, text):
        """Form guidance shares the status line but is not a result to announce."""
        self.status_text.set(text)
        self.status_at = 0.0

    def clear(self):
        for widget in self.content.winfo_children():
            widget.destroy()
        self.photos.clear()
        self.load_form = None
        self.status_bar.pack_forget()
        self.scroll.top()

    def button(self, parent, text, command, kind="Secondary", under=T.SURFACE, large=False, **kwargs):
        def guarded():
            if not self.busy and not self.prompt:
                command()
        return ttk.Button(parent, text=text, command=guarded, style=self.theme.button_style(kind, under, large), **kwargs)

    def device(self, action, done):
        self.busy = True
        self.status_text.set("Waiting for device response...")
        self.root.configure(cursor="watch")
        future = self.executor.submit(action)

        def poll():
            if not future.done():
                self.root.after(50, poll)
                return
            self.busy = False
            self.root.configure(cursor="")
            try:
                result = future.result()
            except Exception as exc:
                result = Result(False, str(exc))
            self.status_text.set(result.message)
            done(result)
        self.root.after(50, poll)

    # -- Guided steps: pharm.dialogs renders prompts in the work panel --------

    def prompt_available(self):
        return self.prompt is None and self.root.winfo_viewable()

    def prompt_context(self):
        return self.context

    def prompt_begin(self, prompt):
        self.prompt = prompt
        overlay = tk.Frame(self.panel, bg=T.SURFACE)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        prompt.overlay = overlay
        self.scan.state(["disabled"])
        return overlay

    def prompt_end(self, prompt):
        prompt.overlay.destroy()
        if self.prompt is prompt:
            self.prompt = None
            self.scan.state(["!disabled"])

    # -- Cabinet --------------------------------------------------------------

    def select(self, number):
        if self.busy or self.prompt or number == self.selected and self.view == "drawer":
            return
        self.selected = number
        self.home()

    def home(self):
        self.clear()
        self.view = "drawer"
        self.context = ""
        compartments = self.store.compartments()
        active = self.store.active()
        if active:
            self.selected = active["compartment"]
        self.draw_cabinet(compartments, active)
        self.drawer_panel(compartments[self.selected - 1], active)
        self.notify()
        if not self.prompt:
            self.scan.focus_set()
        self.update_placeholder()

        expiring = [(d["id"], d["product"]["expiry_date"]) for d in compartments
                    if d["product"] and expiry_note(d["product"]["expiry_date"])[1]]
        notice = tuple(expiring)
        if expiring and notice != self.expiry_notice:
            self.expiry_notice = notice
            dialogs.showwarning("Expiring soon", "These drawers contain packages expiring within 31 days or already expired:\n" +
                                "\n".join(f"Drawer {n}: {expiry}" for n, expiry in expiring) + "\nExpired boxes cannot be dispensed.", parent=self.root)

    def draw_cabinet(self, compartments, active):
        for widget in self.cabinet.winfo_children():
            widget.destroy()
        for index, compartment in enumerate(compartments):
            front = self.drawer_front(compartment, active)
            front.pack(fill="both", expand=True, pady=(self.px(12) if index else 0, 0))

    def drawer_front(self, compartment, active):
        px, theme = self.px, self.theme
        number, product, quantity = compartment["id"], compartment["product"], compartment["quantity"]
        selected = number == self.selected
        state = "selected" if selected else "rest"
        pending = bool(active and active["compartment"] == number)
        is_open = pending or getattr(self.hardware, "selected", None) == number
        tone = "open" if is_open else "stocked" if product and quantity else "empty"
        accents = T.DRAWER_TONES
        frame = ttk.Frame(self.cabinet, style=theme.front_style(state, tone), padding=(px(26 if accents else 22), px(14)),
                          cursor="hand2")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure((0, 1), weight=1)
        line = tk.Frame(frame)
        if pending:
            label(line, "Needs count", "small", T.SHELL_WARNING).pack(side="left")
        elif product:
            note, urgent = expiry_note(product["expiry_date"])
            label(line, f"{quantity} {plural(product.get('unit', ''), quantity)}  ·  ", "small", T.SHELL_MUTED).pack(side="left")
            label(line, note, "small", T.SHELL_DANGER if urgent else T.SHELL_MUTED).pack(side="left")
        if is_open and accents:
            label(line, ("  ·  " if line.winfo_children() else "") + "Open", "small", accents["open"][2]).pack(side="left")
        parts = [
            (label(frame, str(number), "number", accents[tone][2] if accents else T.ACCENT_LINE if selected else T.SHELL_MUTED,
                   anchor="center"),
             dict(row=0, column=0, rowspan=2, sticky="w", padx=(0, px(20)))),
            (label(frame, product.get("generic_name", "Empty") if product else "Empty", "heading",
                   T.SHELL_TEXT if product else T.SHELL_MUTED, wraplength=px(270)),
             dict(row=0, column=1, sticky="sw")),
            (line, dict(row=1, column=1, sticky="nw", pady=(px(2), 0))),
        ]
        painted = [w for w, _ in parts] + line.winfo_children()

        def paint(look):
            bg = theme.front_fill(look, tone)
            frame.configure(style=theme.front_style(look, tone))
            for widget in painted:
                widget.configure(bg=bg)
        for widget, grid in parts:
            widget.grid(**grid)
        for widget in painted:
            widget.configure(cursor="hand2")
        paint(state)

        def inside(event):
            hovered = event.widget.winfo_containing(event.x_root, event.y_root)
            while hovered is not None and hovered is not frame:
                hovered = hovered.master
            return hovered is frame
        for widget in [frame] + painted:
            widget.bind("<Button-1>", lambda _: self.select(number))
            if not selected:
                widget.bind("<Enter>", lambda _: paint("hover"))
                widget.bind("<Leave>", lambda e: None if inside(e) else paint("rest"))
        return frame

    # -- Work panel -----------------------------------------------------------

    def page(self):
        page = tk.Frame(self.content, bg=T.SURFACE, padx=self.px(44), pady=self.px(40))
        page.pack(fill="both", expand=True)
        return page

    def drawer_panel(self, compartment, active):
        px = self.px
        number, product, quantity = compartment["id"], compartment["product"], compartment["quantity"]
        page = self.page()
        caption = label(page, f"DRAWER {number}", "caption", T.ACCENT_DARK)
        caption.pack(anchor="w")
        actions = tk.Frame(page, bg=T.SURFACE)
        actions.pack(side="bottom", fill="x", pady=(px(32), 0))

        if active and active["compartment"] == number:
            caption.configure(text=f"DRAWER {number}  ·  NEEDS COUNT", fg=T.WARNING)
            label(page, f"Count drawer {number}", "display").pack(anchor="w", pady=(px(8), 0))
            label(page, f"A {active['kind']} was interrupted. Check what is physically in the drawer, then record "
                  "what you find. Other drawers stay locked until this is done.", "body", T.TEXT_SOFT,
                  wraplength=px(560)).pack(anchor="w", pady=(px(10), 0))
            recorded = json.loads(active["product"])
            if recorded:
                label(page, f"Recorded: {recorded.get('generic_name', '')}  ·  lot {recorded.get('lot', '')}", "body",
                      T.MUTED, wraplength=px(560)).pack(anchor="w", pady=(px(16), 0))
            if self.role == "admin":
                self.button(actions, f"Count drawer {number}", self.reconcile, "Warning", large=True).pack(side="left")
            return

        if not product:
            label(page, "Empty", "display", T.FAINT).pack(anchor="w", pady=(px(8), 0))
            label(page, "Nothing is in this drawer. Load it before dispensing.", "body",
                  T.MUTED).pack(anchor="w", pady=(px(8), 0))
            # Dispense keeps its place on every drawer; it is unavailable until the drawer holds stock.
            dispense = self.button(actions, "Dispense", lambda: None, "Primary", large=True, width=-12)
            dispense.state(["disabled"])
            dispense.pack(side="left", padx=(0, px(12)))
            load = self.button(actions, f"Load drawer {number}", lambda: self.loading(number), "Secondary", large=True)
            load.pack(side="left")
            if active or self.role != "admin":
                load.state(["disabled"])
            self.blocked_note(page, active)
            return

        name = label(page, product.get("generic_name", ""), "display", wraplength=px(580))
        name.pack(anchor="w", pady=(px(8), 0))
        page.bind("<Configure>", lambda event: name.configure(wraplength=max(px(300), event.width - px(88))), add="+")
        maker = "  ·  ".join(v for v in (product.get("brand_name"), product.get("labeler_name")) if v)
        if maker:
            label(page, maker, "body", T.MUTED, wraplength=px(580)).pack(anchor="w", pady=(px(4), 0))

        facts = tk.Frame(page, bg=T.SURFACE)
        facts.pack(anchor="w", pady=(px(28), 0))
        lots = sorted({i["product"]["lot"] for i in compartment["items"]}) or [product["lot"]]
        note, urgent = expiry_note(product["expiry_date"])
        days = expiry_days(product["expiry_date"])
        for index, (value, font, caption_text, color) in enumerate((
                (str(quantity), "metric", f"{plural(product.get('unit', ''), quantity)} in drawer", T.TEXT),
                (product["expiry_date"], "title", note.lower() if urgent and days >= 0 else "expired" if urgent else "expires",
                 T.DANGER if urgent else T.TEXT),
                (", ".join(lots), "title", "lots" if len(lots) > 1 else "lot", T.TEXT))):
            if index:
                tk.Frame(facts, width=1, bg=T.BORDER).pack(side="left", fill="y", padx=px(28))
            cell = tk.Frame(facts, bg=T.SURFACE)
            cell.pack(side="left", anchor="s")
            label(cell, value, font, color, wraplength=px(200)).pack(anchor="w")
            label(cell, caption_text, "body", T.DANGER if urgent and index == 1 else T.MUTED).pack(anchor="w")
        label(page, f"Package ID  {product['ndc']}", "mono", T.MUTED).pack(anchor="w", pady=(px(24), 0))
        self.label_photo(page, number, product)

        row = tk.Frame(actions, bg=T.SURFACE)
        row.pack(fill="x")
        for text, command, kind in (("Dispense", lambda: self.dispense(number), "Primary"),
                                    ("Load more", lambda: self.loading(number), "Secondary")):
            button = self.button(row, text, command, kind, large=True, width=-12)
            button.pack(side="left", padx=(0, px(12)))
            if active or (text != "Dispense" and self.role != "admin"):
                button.state(["disabled"])
        links = tk.Frame(actions, bg=T.SURFACE)
        links.pack(fill="x", pady=(px(14), 0))
        unload = self.button(links, "Unload drawer", lambda: self.unload(number), "Ghost")
        unload.pack(side="left")
        if active or self.role != "admin":
            unload.state(["disabled"])
        self.button(links, "Box records", lambda: self.box_records(number), "Ghost").pack(side="left", padx=(px(6), 0))
        self.blocked_note(page, active)

    def label_photo(self, page, number, product):
        """The package label photo (click to enlarge), or a quiet slot offering to download one."""
        px = self.px
        image = self.photo(product["ndc"], px(520), px(150))
        if not image:
            slot = ttk.Frame(page, style=self.theme.frame_style("PhotoSlot.TFrame", T.SUBTLE, T.SURFACE),
                             padding=(px(18), px(10)))
            slot.pack(anchor="w", pady=(px(20), 0))
            label(slot, "No label photo saved", "body", T.MUTED, bg=T.SUBTLE).pack(side="left")
            self.button(slot, "Download photo", lambda: self.package_photo(number), "Ghost",
                        under=T.SUBTLE).pack(side="left", padx=(px(10), 0))
            return
        frame = ttk.Frame(page, style=self.theme.frame_style("Photo.TFrame", T.SURFACE, T.SURFACE, outline=T.BORDER),
                          padding=px(10), cursor="hand2")
        frame.pack(anchor="w", pady=(px(20), 0))
        picture = tk.Label(frame, image=image, bg=T.SURFACE, bd=0, cursor="hand2")
        picture.pack()

        def enlarge(_event):
            if not self.busy and not self.prompt:
                self.package_photo(number)
        frame.bind("<Button-1>", enlarge)
        picture.bind("<Button-1>", enlarge)

    def blocked_note(self, page, active):
        if active:
            note = tk.Frame(page, bg=T.SURFACE)
            note.pack(anchor="w", pady=(self.px(24), 0))
            label(note, f"Drawer {active['compartment']} needs a count first.", "strong", T.WARNING).pack(side="left")
            self.button(note, f"Go to drawer {active['compartment']}", lambda: self.select(active["compartment"]),
                        "Ghost").pack(side="left", padx=(self.px(8), 0))

    def find(self, _event=None):
        """Scan a package in the top bar to jump to its drawer and dispense."""
        scan = self.scan.get().strip()
        self.scan.delete(0, "end")
        self.update_placeholder()
        if self.busy or self.prompt or not scan:
            return "break"
        active = self.store.active()
        if active:
            self.status_text.set(f"Count drawer {active['compartment']} first.")
            return "break"
        matches = []
        for drawer in self.store.compartments():
            try:
                if drawer["product"] and self.catalog.matches(scan, drawer["product"]["ndc"]):
                    matches.append(drawer["id"])
            except ValueError:
                pass
        if not matches:
            self.status_text.set("That package is not in any drawer.")
            return "break"
        number = matches[0]
        if len(matches) > 1:
            number = dialogs.askinteger("Choose a drawer", f"This package is in drawers {', '.join(map(str, matches))}. "
                                        "Which one?", parent=self.root, minvalue=min(matches), maxvalue=max(matches))
            if number not in matches:
                return "break"
        self.selected = number
        self.home()
        self.dispense(number)
        return "break"

    def package_photo(self, number):
        product = self.store.compartments()[number - 1]["product"]
        if not product:
            return
        self.context = f"Drawer {number}"
        image = self.photo(product["ndc"], self.px(680), self.px(420))
        if image:
            dialogs.showimage("Package photo", product["generic_name"], image, parent=self.root)
        elif dialogs.askyesno("Package photo", "No photo is saved for this package. Download one from DailyMed?",
                              parent=self.root, yes="Download", no="Cancel"):
            self.fetch_photo(number)

    def photo(self, ndc, width, height):
        path = cached(self.store.path.parent / "images", ndc) or cached(ROOT / "UI/images", ndc)
        if not path:
            return None
        try:
            try:
                from PIL import Image, ImageTk
                with Image.open(path) as original:
                    original.thumbnail((width, height))
                    photo = ImageTk.PhotoImage(original.copy())
            except ImportError:
                photo = tk.PhotoImage(file=str(path))
                scale = max(1, -(-photo.width() // width), -(-photo.height() // height))
                photo = photo.subsample(scale)
        except (OSError, ValueError, tk.TclError):
            return None
        self.photos.append(photo)
        return photo

    # -- Workflows ------------------------------------------------------------

    def start_access(self, kind, number, count, product, done, reason="", items=None):
        try:
            operation = self.store.begin(kind, number, count, product, self.operator, reason, items=items)
            self.store.access(operation, self.operator)
        except ValueError as exc:
            dialogs.showerror("Cannot start", str(exc), parent=self.root)
            return

        def opened(result):
            if not result.ok:
                self.store.cancel(operation, self.operator, result.message,
                                  access_attempted=result.action_attempted)
                title = "Access uncertain" if result.action_attempted else "Arduino connection not ready"
                dialogs.showerror(title, result.message, parent=self.root)
                self.home()
            else:
                done(operation)
        self.device(lambda: self.hardware.open(number), opened)

    def abandon(self, operation, reason):
        self.store.cancel(operation, self.operator, reason)
        dialogs.showwarning("Reconciliation required", "Inventory has not been finalized. Inspect "
                            "the contents and confirm closure before further operations.", parent=self.root)
        self.home()

    def complete(self, operation):
        if not dialogs.askyesno("Confirm closure", "Close the selected drawer. Have you confirmed it is closed?",
                                parent=self.root):
            self.abandon(operation, "Closure was not confirmed")
            return

        self.store.finish(operation, self.operator, closed=True)
        self.lock_after_save()

    def lock_after_save(self):
        """Request locking after saving; a device failure does not undo inventory."""
        def locked(result):
            self.status_text.set("Inventory saved." if result.ok else "Inventory saved. Lock request failed: " + result.message)
            if not result.ok:
                dialogs.showwarning("Inventory saved", "The inventory update was saved, but the lock request failed: " + result.message, parent=self.root)
            self.home()
        self.device(self.hardware.lock, locked)

    def loading(self, number):
        self.clear()
        self.view = "load"
        self.selected = number
        self.context = f"Drawer {number}"
        px, theme = self.px, self.theme
        self.draw_cabinet(self.store.compartments(), self.store.active())
        old = self.store.compartments()[number - 1]["product"]
        page = self.page()
        label(page, f"LOAD  ·  DRAWER {number}", "caption", T.ACCENT_DARK).pack(anchor="w")
        label(page, "Scan the package", "display").pack(anchor="w", pady=(px(8), 0))
        if old:
            label(page, f"Holds {old['generic_name']}. New boxes must be the same package.", "body", T.MUTED,
                  wraplength=px(600)).pack(anchor="w", pady=(px(6), 0))
        row = tk.Frame(page, bg=T.SURFACE)
        row.pack(fill="x", pady=(px(20), 0))
        scan = ttk.Entry(row, font=theme.font("scan"))
        scan.pack(side="left", fill="x", expand=True)
        fields = {}
        scanned = [None]
        serial_text = tk.StringVar()
        self.hint(self.catalog.warning or "Scan a barcode, or type the package ID and press Enter.")

        def search():
            if self.busy:
                return
            try:
                product, notice = self.catalog.loading_details(scan.get())
                parsed = read_scan(scan.get())
                # A top-up scan for the existing package preserves its lot and
                # counted unit. A different package clears those stock fields.
                if old and self.catalog.matches(scan.get(), old["ndc"]):
                    product = dict(old)
                    product.update({k: parsed[k] for k in ("lot", "expiry_date") if parsed[k]})
                    notice = "Existing package matched. Review its lot, expiration and unit before topping up."
                scanned[0] = parsed
                serial_text.set("Serial " + parsed["serial"] if parsed["serial"] else "")
                for key, entry in fields.items():
                    entry.delete(0, "end")
                    entry.insert(0, product.get(key, ""))
                self.hint(notice)
            except ValueError as exc:
                dialogs.showerror("Lookup", str(exc), parent=self.root)
        lookup = self.button(row, "Look up", search)
        lookup.pack(side="left", fill="y", padx=(px(10), 0))
        scan.bind("<Return>", lambda _: search())
        notes = tk.Frame(page, bg=T.SURFACE)
        notes.pack(fill="x", pady=(px(8), 0))
        label(notes, font="body", fg=T.MUTED, textvariable=self.status_text, wraplength=px(520)).pack(side="left")
        label(notes, font="body", fg=T.MUTED, textvariable=serial_text).pack(side="right")

        divider(page).pack(fill="x", pady=(px(24), px(4)))
        grid = tk.Frame(page, bg=T.SURFACE)
        grid.pack(fill="x")
        extra = tk.Frame(page, bg=T.SURFACE)
        for target in (grid, extra):
            target.columnconfigure((0, 1), weight=1, uniform="fields")
        position = {grid: [0, 0], extra: [0, 0]}
        for key, text, span, optional in FIELDS:
            target = extra if optional else grid
            row_index, column = position[target]
            if span == 2 and column:
                row_index, column = row_index + 1, 0
            cell = tk.Frame(target, bg=T.SURFACE)
            cell.grid(row=row_index, column=column, columnspan=span, sticky="ew", pady=(px(16), 0),
                      padx=(px(10) if column else 0, px(10) if span == 1 and not column else 0))
            label(cell, text, "strong", T.TEXT_SOFT).pack(anchor="w")
            entry = ttk.Entry(cell, font=theme.font("input"))
            entry.pack(fill="x", pady=(px(6), 0))
            entry.insert(0, old.get(key, ""))
            fields[key] = entry
            column += span
            position[target] = [row_index + 1, 0] if column >= 2 else [row_index, column]

        def toggle_details():
            if extra.winfo_ismapped():
                extra.pack_forget()
                details.configure(text="Show more details")
            else:
                extra.pack(fill="x", after=details)
                details.configure(text="Hide details")
        details = self.button(page, "Show more details", toggle_details, "Ghost")
        details.pack(anchor="w", pady=(px(14), 0))
        scan.focus_set()

        def load():
            product = {key: entry.get() for key, entry in fields.items()}
            count = dialogs.askinteger("Load quantity", "How many counted units are you adding?", minvalue=1, parent=self.root)
            if count is None:
                return
            items = None
            if scanned[0]:
                first = scanned[0]
                if scan.get().strip() != first["original_scan"] or not self.catalog.matches(first["original_scan"], product["ndc"]):
                    dialogs.showerror("Package identity", "Use the scan again and confirm the package details.", parent=self.root)
                    return
                items = [{"product": product, "scan": first["original_scan"], "package_ndc": identifier(product["ndc"])}]
                for index in range(1, count):
                    next_scan = dialogs.askstring("Scan each unit", f"Scan package {index + 1} of {count} before loading.",
                                                  parent=self.root, scan=True)
                    if next_scan is None:
                        return
                    if not self.catalog.matches(next_scan, product["ndc"]):
                        dialogs.showerror("Different package", "All units must have the same package identity.", parent=self.root)
                        return
                    parsed = read_scan(next_scan)
                    item_product = {**product, **{k: parsed[k] for k in ("lot", "expiry_date") if parsed[k]}}
                    items.append({"product": item_product, "scan": next_scan, "package_ndc": identifier(product["ndc"])})

            def opened(operation):
                if not dialogs.askyesno("Confirm placement", f"Place exactly {count} {product['unit']} of the verified product and lot "
                                        f"in drawer {number}. Is placement complete?", parent=self.root):
                    self.abandon(operation, "Placement not confirmed")
                    return
                self.complete(operation)
            self.start_access("load", number, count, product, opened, items=items)

        footer = tk.Frame(page, bg=T.SURFACE)
        footer.pack(fill="x", pady=(px(32), 0))
        submit = self.button(footer, "Confirm and load", load, "Primary", large=True)
        submit.pack(side="left")
        self.button(footer, "Cancel", self.home, large=True).pack(side="left", padx=(px(12), 0))
        self.load_form = {"scan": scan, "fields": fields, "lookup": lookup, "load": submit}

    def dispense(self, number):
        self.context = f"Drawer {number}"
        item = self.store.compartments()[number - 1]
        product = item["product"]
        count = dialogs.askinteger("Dispense", f"How many {plural(product.get('unit', 'unit'), 2)} of {product.get('generic_name', 'this product')}? "
                                   f"{item['quantity']} in the drawer.", minvalue=1, maxvalue=item["quantity"], parent=self.root,
                                   initialvalue=1)
        if count is None:
            return

        def opened(operation):
            for index in range(self.store.operation(operation)["verified"], count):
                scan = dialogs.askstring("Verify package", f"Scan item {index + 1} of {count}: {product['generic_name']} "
                                         f"({product['ndc']}). Submit an empty scan to request drawer access again.",
                                         parent=self.root, scan=True)
                if scan is not None and not scan.strip():
                    if not dialogs.askyesno("Reopen drawer", "Request one new access command for this drawer?", parent=self.root):
                        self.abandon(operation, "Reopening cancelled")
                        return
                    number = self.store.note_reopen(operation, self.operator)

                    def reopened(result):
                        if result.ok:
                            opened(operation)
                        else:
                            self.abandon(operation, result.message)
                    self.device(lambda: self.hardware.open(number), reopened)
                    return
                try:
                    valid = scan is not None and self.catalog.matches(scan, product["ndc"])
                except ValueError:
                    valid = False
                if not valid:
                    self.abandon(operation, f"Scan cancelled or mismatched after {index} verified items")
                    return
                try:
                    self.store.verify_one(operation, self.operator, scan, package_ndc=identifier(product["ndc"]))
                except ValueError as exc:
                    self.abandon(operation, str(exc))
                    return
            if not dialogs.askyesno("Confirm removal", f"Have exactly {count} {product['unit']} been removed?", parent=self.root):
                self.abandon(operation, "Removal count uncertain")
                return
            self.complete(operation)
        self.start_access("dispense", number, count, {}, opened)

    def unload(self, number):
        self.context = f"Drawer {number}"
        if not dialogs.askyesno("Unload", f"Remove all stock from drawer {number}?", parent=self.root,
                                yes="Unload drawer", no="Cancel", danger=True):
            return

        def opened(operation):
            if dialogs.askyesno("Confirm empty", "Have all contents been removed and the drawer checked empty?", parent=self.root):
                self.complete(operation)
            else:
                self.abandon(operation, "Unload incomplete")
        self.start_access("unload", number, 0, {}, opened)

    def manual(self):
        self.context = ""
        number = dialogs.askinteger("Unlock a drawer", "Which drawer? (1 to 4)", minvalue=1, maxvalue=4, parent=self.root)
        if number is None:
            return
        self.context = f"Drawer {number}"
        reason = dialogs.askstring("Unlock a drawer", "Why does it need to be opened?", parent=self.root)
        if not reason:
            return
        self.start_access("manual", number, 0, {}, lambda op: self.abandon(op, "Manual inspection requires a count"), reason)

    def reconcile(self):
        active = self.store.active()
        if not active:
            self.home()
            return
        self.context = f"Drawer {active['compartment']}"
        product = json.loads(active["product"])
        candidates = self.store.reconciliation_items(active["id"])
        remaining_ids = None
        if any(i["serial"] for i in candidates) or len({json.dumps(i["product"], sort_keys=True) for i in candidates}) > 1:
            # Serial numbers or mixed lots: a count alone cannot identify the boxes.
            choices = [f"Lot {i['product']['lot']}  ·  expires {i['product']['expiry_date']}  ·  serial {i['serial'] or 'not recorded'}"
                       for i in candidates]
            selected = dialogs.askchoices("Count drawer", "Tick each box that is physically in the drawer. Remove anything else.",
                                          choices, parent=self.root)
            if selected is None:
                return
            remaining_ids = [candidates[n]["id"] for n in selected]
            count = len(remaining_ids)
        else:
            count = dialogs.askinteger("Count drawer", f"How many of {product.get('generic_name', 'the recorded product')} "
                                       f"(lot {product.get('lot', 'unknown')}) are physically in the drawer? "
                                       "Remove anything else first.", minvalue=0, parent=self.root)
            if count is None:
                return
        reason = dialogs.askstring("Count drawer", "What happened? This is recorded in the audit log.", parent=self.root)
        if not reason:
            return
        if not dialogs.askyesno("Closure", "Have you verified the product/lot and physically closed all four drawers?", parent=self.root):
            return

        self.store.reconcile(active["id"], count, self.operator, reason, closed=True, remaining_ids=remaining_ids)
        self.lock_after_save()

    def box_records(self, number):
        self.context = f"Drawer {number}"
        items = self.store.compartments()[number - 1]["items"]
        rows = [(i["product"]["lot"], i["product"]["expiry_date"], i["serial"] or "not recorded") for i in items]
        dialogs.showrecords("Box records", ("Lot", "Expires", "Serial"), rows, parent=self.root,
                            message=f"{len(rows)} recorded {'box' if len(rows) == 1 else 'boxes'}")

    def fetch_photo(self, number):
        product = self.store.compartments()[number - 1]["product"]
        if not product:
            return

        def fetch():
            try:
                fetch_photo(self.store.path.parent / "images", product["ndc"])
                return Result(True, "Reference photo downloaded. It does not identify inventory.")
            except Exception as exc:
                return Result(False, f"Optional photo unavailable: {exc}")
        self.device(fetch, lambda result: self.home())

    def export_audit(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["id", "time", "operator", "operation", "action", "detail"])
                writer.writeheader()
                for row in self.store.audit():
                    writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v
                                     for k, v in row.items()})
            self.status_text.set("Audit exported.")

    def choose_catalog(self):
        path = filedialog.askopenfilename(parent=self.root, title="Choose package catalog",
                                          filetypes=[("JSON catalog", "*.json")])
        if not path:
            return
        catalog = Catalog(path)
        if catalog.warning:
            dialogs.showerror("Catalog unavailable", catalog.warning, parent=self.root)
            return
        # Persist only a validated path, separately for simulation and bench.
        settings = self.store.path.parent / "catalog-path.json"
        temporary = settings.with_suffix(".tmp")
        temporary.write_text(json.dumps(str(Path(path).resolve())), encoding="utf-8")
        temporary.replace(settings)
        self.catalog = catalog
        self.status_text.set(f"Catalog selected: {Path(path).name}")
        self.home()

    def backup(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".sqlite3", filetypes=[("SQLite backup", "*.sqlite3")])
        if path:
            self.store.backup(path)
            self.status_text.set("Consistent database backup created.")

    def close(self):
        if getattr(self, "prompt", None):
            self.prompt.close()  # Closing the window answers the current step with Cancel.
            return
        if self.busy:
            dialogs.showinfo("Please wait", "Wait for the device request to finish before closing.", parent=self.root)
            return
        if self.store.active() and not dialogs.askyesno("Unfinished operation", "An operation still needs reconciliation. It will remain blocked "
                                                        "on restart. Close the application?", parent=self.root):
            return
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.hardware.close()
        self.root.destroy()


def choose_usb_port(root, team=False):
    """Select explicitly. Enumeration is read-only; selection does not open the port."""
    theme = T.apply_theme(root)
    px = theme.px
    dialog = tk.Toplevel(root)
    dialog.title("Connect Arduino Uno / Nano by USB")
    dialog.resizable(False, False)
    dialog.configure(bg=T.SURFACE)
    frame = tk.Frame(dialog, bg=T.SURFACE, padx=px(28), pady=px(26))
    frame.pack(fill="both")
    label(frame, "Select the Arduino's COM port", "heading").pack(anchor="w")
    label(frame, "Select the adapter matching the installed firmware. Selecting a port does not send commands. "
          "Automatic locking on closure still requires verification of the lock/sensors.", "small", T.MUTED,
          wraplength=px(500)).pack(anchor="w", pady=(px(6), px(16)))
    choices = ttk.Combobox(frame, width=56, state="readonly", font=theme.font("body"))
    choices.pack(fill="x")
    notice = tk.StringVar()
    label(frame, font="small", fg=T.TEXT_SOFT, textvariable=notice, wraplength=px(500)).pack(anchor="w", pady=(px(8), 0))
    ports = []
    selected = []

    def refresh():
        nonlocal ports
        choices.set("")
        try:
            ports = usb_ports()
            choices["values"] = [f"{device} | {description}" for device, description in ports]
            notice.set("Select the port shown for your Arduino in Windows Device Manager." if ports else
                       "No serial ports found. Connect the Arduino with a data-capable USB cable, then refresh.")
        except (ValueError, OSError) as exc:
            ports = []
            choices["values"] = []
            notice.set(str(exc))

    ready = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text=("Team pressure-sensor firmware is installed and its wiring is verified." if team else
                                 "Updated MAS/1 firmware is installed and the wiring is verified for bench testing."),
                    variable=ready, style="Check.TCheckbutton").pack(anchor="w", pady=(px(14), 0))

    def select():
        index = choices.current()
        if index < 0 or index >= len(ports) or not ready.get():
            dialogs.showerror("USB setup", "Select a port and confirm bench preparation first.", parent=dialog)
            return
        selected.append(ports[index][0])
        dialog.destroy()

    row = tk.Frame(frame, bg=T.SURFACE)
    row.pack(fill="x", pady=(px(24), 0))
    ttk.Button(row, text="Use selected port", command=select, style=theme.button_style("Primary")).pack(side="left")
    ttk.Button(row, text="Refresh ports", command=refresh, style=theme.button_style("Secondary")).pack(side="left", padx=(px(10), 0))
    ttk.Button(row, text="Cancel", command=dialog.destroy, style=theme.button_style("Secondary")).pack(side="right")
    refresh()
    dialog.update_idletasks()
    dialog.geometry(f"+{(dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2}"
                    f"+{(dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 3}")
    dialog.grab_set()
    root.wait_window(dialog)
    return selected[0] if selected else None


def saved_palette(directory):
    try:
        value = json.loads((directory / "appearance.json").read_text(encoding="utf-8"))
        return value if value in T.PALETTES else "light"
    except (OSError, ValueError):
        return "light"


def save_palette(directory, palette):
    settings = directory / "appearance.json"
    temporary = settings.with_suffix(".tmp")
    temporary.write_text(json.dumps(palette), encoding="utf-8")
    temporary.replace(settings)


def saved_catalog_path(directory, default):
    try:
        value = json.loads((directory / "catalog-path.json").read_text(encoding="utf-8"))
        return Path(value) if isinstance(value, str) and value.strip() else default
    except (OSError, ValueError):
        return default


def use_native_resolution():
    """Render at the display's real resolution. Without this, Windows
    bitmap-stretches the window on scaled displays and text looks blurry."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        # Group the taskbar button under the app's own icon, not Python's.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EPICS.PharmacyDrawer")
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def size_window(root):
    theme = T.apply_theme(root)
    width, height = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(theme.px(1240), int(width * 0.92)), min(theme.px(840), int(height * 0.86))
    root.geometry(f"{w}x{h}+{(width - w) // 2}+{max(0, (height - h) // 2 - theme.px(16))}")
    root.pharm_sized = True


def load_catalog(root, path):
    """Parse the catalog off the UI thread behind a splash screen.

    Returns None if the window is closed while loading."""
    splash = Splash(root)
    root.update()
    result = {}

    def work():
        try:
            result["catalog"] = Catalog(path)
        except BaseException as exc:
            result["error"] = exc
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    done = tk.BooleanVar(root, False)
    closed = []

    def poll():
        if worker.is_alive():
            root.after(40, poll)
        else:
            done.set(True)

    def cancel():
        closed.append(True)
        done.set(True)
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.after(40, poll)
    root.wait_variable(done)
    if closed:
        root.destroy()
        return None
    splash.destroy()
    if "error" in result:
        raise result["error"]
    return result["catalog"]


def main(argv=None):
    parser = argparse.ArgumentParser()
    connection = parser.add_mutually_exclusive_group()
    connection.add_argument("--hardware-bench", action="store_true", help="Legacy Pi HTTPS adapter")
    connection.add_argument("--usb", action="store_true", help="Select an Arduino Uno/Nano COM port for direct USB bench testing")
    connection.add_argument("--team-usb", action="store_true", help="Use the team's byte-echo / pressure-sensor firmware")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--catalog", type=Path, help="Package catalog JSON; otherwise use the saved selection")
    parser.add_argument("--smoke-test", action="store_true", help="Render screens and exit without hardware access")
    args = parser.parse_args(argv)
    if args.smoke_test and (args.hardware_bench or args.usb or args.team_usb):
        parser.error("Smoke tests only run in simulation.")
    mode = "bench" if args.hardware_bench or args.usb or args.team_usb else "simulation"
    directory = args.data_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "EPICS-Pharm" / mode
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=directory / "application.log", level=logging.INFO)
    hardware = HttpHardware(os.environ.get("MAS_API_URL", ""), os.environ.get("MAS_API_KEY", ""),
                            os.environ.get("MAS_CA_FILE")) if args.hardware_bench else Simulator()
    use_native_resolution()
    T.use_palette(saved_palette(directory))
    root = tk.Tk()
    T.apply_theme(root)
    root.title("Pharmacy Drawer")
    set_window_icon(root)
    size_window(root)
    if args.usb or args.team_usb:
        root.withdraw()
        port = choose_usb_port(root, team=args.team_usb)
        if port is None:
            root.destroy()
            return
        hardware = TeamSerialHardware(port) if args.team_usb else SerialHardware(port)
        root.deiconify()
    catalog_path = args.catalog or saved_catalog_path(directory, ROOT / "UI/db.json")
    catalog = load_catalog(root, catalog_path)
    if catalog is None:
        hardware.close()
        return
    app = App(root, Store(directory / "inventory.sqlite3"), catalog, hardware)
    if args.smoke_test:
        root.update()
        app.home()
        root.update()
        app.loading(1)
        root.update()
        app.executor.shutdown(wait=False)
        hardware.close()
        root.destroy()
        print("Password-free four-drawer dashboard and loading form rendered successfully.")
        return
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if sys.stderr is None:  # Windowless launch: no console would show the error.
            from tkinter import messagebox
            messagebox.showerror("Pharmacy Drawer could not start", f"{exc}\n\nSee docs/RUNNING.md.")
        raise
