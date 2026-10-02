"""Dependency-free Tkinter UI. All hardware I/O runs outside the UI thread."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import logging
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .catalog import Catalog
from .hardware import HttpHardware, Simulator, SerialHardware, usb_ports
from .store import Store
from .barcodes import read_scan
from .catalog import identifier
from .team_hardware import TeamSerialHardware
from .photos import cached, fetch_photo

ROOT = Path(__file__).resolve().parents[1]


class App:
    def __init__(self, root, store, catalog, hardware):
        self.root, self.store, self.catalog, self.hardware = root, store, catalog, hardware
        self.operator = None
        self.role = None
        self.busy = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        root.title("EPICS Pharmacy Drawer")
        from UI.theme import apply_theme
        apply_theme(root)
        root.geometry("1000x740")
        root.minsize(780, 620)
        root.bind("<Escape>", lambda _: root.attributes("-fullscreen", False))
        root.bind("<F11>", lambda _: root.attributes("-fullscreen", not root.attributes("-fullscreen")))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error
        self.status_text = tk.StringVar(value="Ready")
        self.expiry_notice = None
        banner = ("SIMULATION | Try the complete workflow without connected hardware." if isinstance(hardware, Simulator)
                  else f"{hardware.mode} | Closure requires manual confirmation.")
        ttk.Label(root, text=banner,
                  foreground="#a34000", padding=10).pack(fill="x")
        ttk.Label(root, textvariable=self.status_text, padding=8, wraplength=940).pack(side="bottom", fill="x")
        self.content = ttk.Frame(root, padding=18)
        self.content.pack(fill="both", expand=True)
        self.operator = self.store.start_local_session()
        self.role = "admin"
        self.home()

    def callback_error(self, kind, value, traceback):
        logging.error("UI callback failed", exc_info=(kind, value, traceback))
        messagebox.showerror("Action failed", f"{value}\nAny unfinished access remains available for reconciliation.", parent=self.root)

    def clear(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def button(self, parent, label, command, **kwargs):
        def guarded():
            if not self.busy:
                command()
        button = ttk.Button(parent, text=label, command=guarded, **kwargs)
        return button

    def device(self, action, done):
        self.busy = True
        self.status_text.set("Waiting for device response...")
        future = self.executor.submit(action)

        def poll():
            if not future.done():
                self.root.after(50, poll)
                return
            self.busy = False
            try:
                result = future.result()
            except Exception as exc:
                from .hardware import Result
                result = Result(False, str(exc))
            self.status_text.set(result.message)
            done(result)
        self.root.after(50, poll)

    def home(self):
        self.clear()
        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Four drawers | No password required", font=("Segoe UI", 16)).pack(side="left")
        self.button(toolbar, "Device status", lambda: self.device(self.hardware.status, lambda r: None)).pack(side="right")
        ttk.Label(self.content, text=self.catalog.warning or "Catalog loaded. Search requires an exact package match.",
                  wraplength=900).pack(anchor="w", pady=12)
        active = self.store.active()
        if active:
            ttk.Label(self.content, text=f"ACTION REQUIRED: drawer {active['compartment']} has an unfinished "
                      f"{active['kind']} operation. Verified scans: {active['verified']}. Reconcile before continuing.",
                      foreground="#a34000", wraplength=900).pack(fill="x", pady=10)
            if self.role == "admin":
                self.button(self.content, "Reconcile physical contents", self.reconcile).pack(anchor="w")
        cards = ttk.Frame(self.content)
        cards.pack(fill="both", expand=True, pady=12)
        for index, compartment in enumerate(self.store.compartments()):
            number, product = compartment["id"], compartment["product"]
            frame = ttk.LabelFrame(cards, text=f"Drawer {number}", padding=14)
            frame.grid(row=index // 2, column=index % 2, sticky="nsew", padx=8, pady=8)
            cards.columnconfigure(index % 2, weight=1)
            cards.rowconfigure(index // 2, weight=1)
            ttk.Label(frame, text=product.get("generic_name", "EMPTY"), font=("Segoe UI", 15), wraplength=360).pack(anchor="w")
            details = f"Quantity: {compartment['quantity']} {product.get('unit', '')}"
            if product:
                details += f"\nPackage: {product['ndc']}\nLot: {product['lot']} | Expires: {product['expiry_date']}"
                lots = sorted({i["product"]["lot"] for i in compartment["items"]})
                if len(lots) > 1:
                    details += "\nLots: " + ", ".join(lots)
            ttk.Label(frame, text=details, wraplength=370).pack(anchor="w", pady=8)
            if product:
                self.show_photo(frame, product["ndc"])
            row = ttk.Frame(frame)
            row.pack(anchor="w")
            for label, command in (("Dispense", lambda n=number: self.dispense(n)),
                                   ("Load / top up", lambda n=number: self.loading(n)),
                                   ("Unload", lambda n=number: self.unload(n))):
                button = self.button(row, label, command)
                button.pack(side="left", padx=3)
                if active or (label != "Dispense" and self.role != "admin") or (label != "Load / top up" and not product):
                    button.state(["disabled"])
            if product:
                extras = ttk.Frame(frame)
                extras.pack(anchor="w", pady=5)
                self.button(extras, "Box records", lambda n=number: self.box_records(n)).pack(side="left")
                self.button(extras, "Fetch photo", lambda n=number: self.fetch_photo(n)).pack(side="left", padx=3)
        if self.role == "admin":
            actions = ttk.Frame(self.content)
            actions.pack(fill="x")
            for label, command in (("Manual access", self.manual),
                                   ("Choose catalog", self.choose_catalog),
                                   ("Export audit", self.export_audit), ("Backup", self.backup)):
                self.button(actions, label, command).pack(side="left", padx=5)
        from datetime import date, timedelta
        expiring = [(d["id"], d["product"]["expiry_date"]) for d in self.store.compartments()
                    if d["product"] and date.fromisoformat(d["product"]["expiry_date"]) <= date.today() + timedelta(days=31)]
        notice = tuple(expiring)
        if expiring and notice != self.expiry_notice:
            self.expiry_notice = notice
            messagebox.showwarning("Expiring soon", "These drawers contain packages expiring within 31 days or already expired:\n" +
                                   "\n".join(f"Drawer {n}: {expiry}" for n, expiry in expiring) + "\nExpired boxes cannot be dispensed.", parent=self.root)

    def start_access(self, kind, number, count, product, done, reason="", items=None):
        try:
            operation = self.store.begin(kind, number, count, product, self.operator, reason, items=items)
            self.store.access(operation, self.operator)
        except ValueError as exc:
            messagebox.showerror("Cannot start", str(exc), parent=self.root)
            return

        def opened(result):
            if not result.ok:
                self.store.cancel(operation, self.operator, result.message,
                                  access_attempted=result.action_attempted)
                title = "Access uncertain" if result.action_attempted else "Arduino connection not ready"
                messagebox.showerror(title, result.message, parent=self.root)
                self.home()
            else:
                done(operation)
        self.device(lambda: self.hardware.open(number), opened)

    def abandon(self, operation, reason):
        self.store.cancel(operation, self.operator, reason)
        messagebox.showwarning("Reconciliation required", "Inventory has not been finalized. Inspect "
                               "the contents and confirm closure before further operations.", parent=self.root)
        self.home()

    def complete(self, operation):
        if not messagebox.askyesno("Confirm closure", "Close the selected drawer. Have you confirmed it is closed?",
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
                messagebox.showwarning("Inventory saved", "The inventory update was saved, but the lock request failed: " + result.message, parent=self.root)
            self.home()
        self.device(self.hardware.lock, locked)

    def loading(self, number):
        self.clear()
        ttk.Label(self.content, text=f"Load drawer {number}", font=("Segoe UI", 20)).grid(row=0, column=0, columnspan=2, pady=10)
        ttk.Label(self.content, text="Scan package identifier").grid(row=1, column=0, sticky="w")
        scan = ttk.Entry(self.content, width=45)
        scan.grid(row=1, column=1, sticky="ew")
        fields = {}
        scanned = [None]
        serial_text = tk.StringVar()
        labels = {"generic_name": "Medication name / strength / form", "ndc": "Package identifier",
                  "lot": "Lot number", "expiry_date": "Actual package expiration (YYYY-MM-DD)",
                  "unit": "Counted unit (e.g. bottle, box, tablet)", "description": "Package description",
                  "brand_name": "Brand", "labeler_name": "Labeler"}
        old = self.store.compartments()[number - 1]["product"]
        for row, (key, label) in enumerate(labels.items(), start=3):
            ttk.Label(self.content, text=label).grid(row=row, column=0, sticky="w", pady=7)
            entry = ttk.Entry(self.content, width=50)
            entry.grid(row=row, column=1, sticky="ew", pady=7)
            entry.insert(0, old.get(key, ""))
            fields[key] = entry

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
                serial_text.set("Serial: " + (parsed["serial"] or "not encoded"))
                for key, entry in fields.items():
                    entry.delete(0, "end")
                    entry.insert(0, product.get(key, ""))
                self.status_text.set(notice)
            except ValueError as exc:
                messagebox.showerror("Lookup", str(exc), parent=self.root)
        self.button(self.content, "Use scan / look up", search).grid(row=2, column=1, sticky="w")
        scan.bind("<Return>", lambda _: search())
        scan.focus_set()

        def load():
            product = {key: entry.get() for key, entry in fields.items()}
            count = simpledialog.askinteger("Load quantity", "How many counted units are you adding?", minvalue=1, parent=self.root)
            if count is None:
                return
            items = None
            if scanned[0]:
                first = scanned[0]
                if scan.get().strip() != first["original_scan"] or not self.catalog.matches(first["original_scan"], product["ndc"]):
                    messagebox.showerror("Package identity", "Use the scan again and confirm the package details.", parent=self.root)
                    return
                items = [{"product": product, "scan": first["original_scan"], "package_ndc": identifier(product["ndc"])}]
                for index in range(1, count):
                    next_scan = simpledialog.askstring("Scan each unit", f"Scan package {index + 1} of {count} before loading.", parent=self.root)
                    if next_scan is None:
                        return
                    if not self.catalog.matches(next_scan, product["ndc"]):
                        messagebox.showerror("Different package", "All units must have the same package identity.", parent=self.root)
                        return
                    parsed = read_scan(next_scan)
                    item_product = {**product, **{k: parsed[k] for k in ("lot", "expiry_date") if parsed[k]}}
                    items.append({"product": item_product, "scan": next_scan, "package_ndc": identifier(product["ndc"])})

            def opened(operation):
                if not messagebox.askyesno("Confirm placement", f"Place exactly {count} {product['unit']} of the verified product and lot "
                                           f"in drawer {number}. Is placement complete?", parent=self.root):
                    self.abandon(operation, "Placement not confirmed")
                    return
                self.complete(operation)
            self.start_access("load", number, count, product, opened, items=items)
        self.button(self.content, "Confirm details and load", load).grid(row=12, column=1, pady=16, sticky="w")
        self.button(self.content, "Back", self.home).grid(row=12, column=0)
        ttk.Label(self.content, textvariable=serial_text).grid(row=13, column=1, sticky="w")
        self.content.columnconfigure(1, weight=1)

    def dispense(self, number):
        item = self.store.compartments()[number - 1]
        product = item["product"]
        count = simpledialog.askinteger("Dispense", f"How many {product.get('unit', 'units')}?", minvalue=1,
                                        maxvalue=item["quantity"], parent=self.root)
        if count is None:
            return

        def opened(operation):
            for index in range(self.store.operation(operation)["verified"], count):
                scan = simpledialog.askstring("Verify package", f"Scan item {index + 1} of {count}: {product['generic_name']} "
                                              f"({product['ndc']}). Submit an empty scan to request drawer access again.", parent=self.root)
                if scan is not None and not scan.strip():
                    if not messagebox.askyesno("Reopen drawer", "Request one new access command for this drawer?", parent=self.root):
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
            if not messagebox.askyesno("Confirm removal", f"Have exactly {count} {product['unit']} been removed?", parent=self.root):
                self.abandon(operation, "Removal count uncertain")
                return
            self.complete(operation)
        self.start_access("dispense", number, count, {}, opened)

    def unload(self, number):
        if not messagebox.askyesno("Unload", f"Remove all stock from drawer {number}?", parent=self.root):
            return

        def opened(operation):
            if messagebox.askyesno("Confirm empty", "Have all contents been removed and the drawer checked empty?", parent=self.root):
                self.complete(operation)
            else:
                self.abandon(operation, "Unload incomplete")
        self.start_access("unload", number, 0, {}, opened)

    def manual(self):
        number = simpledialog.askinteger("Manual access", "Drawer number", minvalue=1, maxvalue=4, parent=self.root)
        if number is None:
            return
        reason = simpledialog.askstring("Manual access", "Reason for access", parent=self.root)
        if not reason:
            return
        self.start_access("manual", number, 0, {}, lambda op: self.abandon(op, "Manual inspection requires a count"), reason)

    def reconcile(self):
        active = self.store.active()
        if not active:
            self.home()
            return
        product = json.loads(active["product"])
        count = simpledialog.askinteger("Reconcile", f"Inspect drawer {active['compartment']}. Count only the recorded product/lot:\n"
                                        f"{product.get('generic_name', 'Unidentified: remove all stock')} / {product.get('lot', '')}\n"
                                        "Remove any other stock. Enter the actual remaining count.", minvalue=0, parent=self.root)
        if count is None:
            return
        remaining_ids = None
        candidates = self.store.reconciliation_items(active["id"])
        if count and (any(i["serial"] for i in candidates) or len({json.dumps(i["product"], sort_keys=True) for i in candidates}) > 1):
            choices = "\n".join(f"{n}: lot {i['product']['lot']}, expires {i['product']['expiry_date']}, serial {i['serial'] or 'not recorded'}"
                                  for n, i in enumerate(candidates, start=1))
            selected = simpledialog.askstring("Remaining box records", choices + "\n\nEnter the numbers of boxes physically present, separated by commas.", parent=self.root)
            if selected is None:
                return
            try:
                indexes = [int(value.strip()) for value in selected.split(",")]
                if any(n < 1 or n > len(candidates) for n in indexes) or len(indexes) != count or len(set(indexes)) != count:
                    raise ValueError()
                remaining_ids = [candidates[n - 1]["id"] for n in indexes]
            except ValueError:
                messagebox.showerror("Box records", "Select exactly the recorded remaining boxes.", parent=self.root)
                return
        reason = simpledialog.askstring("Reconcile", "Explain the discrepancy or interrupted operation", parent=self.root)
        if not reason:
            return
        if not messagebox.askyesno("Closure", "Have you verified the product/lot and physically closed all four drawers?", parent=self.root):
            return

        self.store.reconcile(active["id"], count, self.operator, reason, closed=True, remaining_ids=remaining_ids)
        self.lock_after_save()

    def show_photo(self, frame, ndc):
        path = cached(self.store.path.parent / "images", ndc) or cached(ROOT / "UI/images", ndc)
        if not path:
            return
        try:
            try:
                from PIL import Image, ImageTk
                with Image.open(path) as original:
                    original.thumbnail((110, 65))
                    photo = ImageTk.PhotoImage(original.copy())
            except ImportError:
                photo = tk.PhotoImage(file=str(path))
                scale = max(1, (photo.width() + 109) // 110, (photo.height() + 64) // 65)
                photo = photo.subsample(scale)
            label = ttk.Label(frame, image=photo)
            label.image = photo
            label.pack(anchor="w")
        except (OSError, ValueError, tk.TclError):
            pass

    def box_records(self, number):
        items = self.store.compartments()[number - 1]["items"]
        message = "\n".join(f"Lot: {i['product']['lot']} | Expires: {i['product']['expiry_date']} | Serial: {i['serial'] or 'not recorded'}"
                            for i in items[:40])
        if len(items) > 40:
            message += f"\n{len(items) - 40} more records are available in the browser interface."
        messagebox.showinfo(f"Drawer {number} box records", message or "Empty", parent=self.root)

    def fetch_photo(self, number):
        product = self.store.compartments()[number - 1]["product"]
        if not product:
            return
        from .hardware import Result
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
            messagebox.showerror("Catalog unavailable", catalog.warning, parent=self.root)
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
        if self.busy:
            messagebox.showinfo("Please wait", "Wait for the device request to finish before closing.", parent=self.root)
            return
        if self.store.active() and not messagebox.askyesno("Unfinished operation", "An operation still needs reconciliation. It will remain blocked "
                                                         "on restart. Close the application?", parent=self.root):
            return
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.hardware.close()
        self.root.destroy()


def choose_usb_port(root, team=False):
    """Select explicitly. Enumeration is read-only; selection does not open the port."""
    dialog = tk.Toplevel(root)
    dialog.title("Connect Arduino Uno / Nano by USB")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=20)
    frame.pack()
    ttk.Label(frame, text="Select the Arduino's COM port", font=("Segoe UI", 16)).pack(anchor="w", pady=8)
    choices = ttk.Combobox(frame, width=64, state="readonly")
    choices.pack(fill="x", pady=8)
    notice = tk.StringVar()
    ttk.Label(frame, textvariable=notice, wraplength=500).pack(anchor="w", pady=8)
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
                    variable=ready).pack(anchor="w", pady=12)
    ttk.Label(frame, text="Select the adapter matching the installed firmware. Selecting a port does not send commands. "
              "Automatic locking on closure still requires verification of the lock/sensors.", wraplength=500).pack(anchor="w", pady=8)

    def select():
        index = choices.current()
        if index < 0 or index >= len(ports) or not ready.get():
            messagebox.showerror("USB setup", "Select a port and confirm bench preparation first.", parent=dialog)
            return
        selected.append(ports[index][0])
        dialog.destroy()

    row = ttk.Frame(frame)
    row.pack(fill="x", pady=8)
    ttk.Button(row, text="Refresh ports", command=refresh).pack(side="left")
    ttk.Button(row, text="Use selected port", command=select).pack(side="left", padx=8)
    ttk.Button(row, text="Cancel", command=dialog.destroy).pack(side="right")
    refresh()
    dialog.grab_set()
    root.wait_window(dialog)
    return selected[0] if selected else None


def saved_catalog_path(directory, default):
    try:
        value = json.loads((directory / "catalog-path.json").read_text(encoding="utf-8"))
        return Path(value) if isinstance(value, str) and value.strip() else default
    except (OSError, ValueError):
        return default


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
    root = tk.Tk()
    if args.usb or args.team_usb:
        root.withdraw()
        port = choose_usb_port(root, team=args.team_usb)
        if port is None:
            root.destroy()
            return
        hardware = TeamSerialHardware(port) if args.team_usb else SerialHardware(port)
        root.deiconify()
    catalog_path = args.catalog or saved_catalog_path(directory, ROOT / "UI/db.json")
    app = App(root, Store(directory / "inventory.sqlite3"), Catalog(catalog_path), hardware)
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
    main()
