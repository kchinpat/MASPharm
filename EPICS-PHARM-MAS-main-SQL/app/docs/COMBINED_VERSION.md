# Combined version, September 30, 2026

The repaired directory is the maintained combined application. It includes the team's browser design, GS1 scanning, individual box tracking, photos and pressure-sensor firmware support, alongside transactional inventory, recovery, audit export, backups, manual entry and exact catalog matching.

## Start the interfaces

The project folder's four launchers start these; everything else is in its `app` folder.

- **Pharmacy Drawer.exe** opens the desktop in simulation without a console window. A startup error is shown in a message box.
- **Browser Cabinet.exe** starts the local browser server and opens `http://127.0.0.1:8000`. Keep its console open; closing the server stops the browser interface. It opens in UI two, the Console layout, where every drawer stays in view. **Switch to legacy UI** in **Menu** changes to the earlier layout, with the drawers stacked beside one work panel, and **Switch to new UI** switches back. Both run the same workflows. **Light theme** and **Dark theme** in **Menu** change the UI showing: UI two is dark until light is chosen, and the legacy UI light until dark is chosen. The browser remembers the layout and each layout's theme. The desktop app has the same items in its **Menu**; the desktop and the browser each remember their own choices.
- **USB Bench.exe** selects a port for repaired MAS/1 firmware. Its console shows hardware diagnostics.
- **Team USB Bench.exe** selects a port for the team's pressure-sensor/byte-echo firmware.

The included `runtime-dependencies.zip` supplies the browser, USB and Pi API dependencies without a local virtual environment. It retains the package sources, licenses and metadata, and Python imports it directly without extraction. Keep it with the project. Python 3.10+ with Tcl/Tk and SQLite is still required. For a source-only copy without the bundle, install the optional dependencies (Flask, pyserial, and Pillow for JPEG display in the desktop) with the same Python used to launch the app:

```powershell
python -m pip install -r requirements.txt
```

From the `app` folder:

```powershell
python -m pharm.app
python -m pharm.web
python -m pharm.web --usb-port COM3
python -m pharm.web --team-usb-port COM3
python -m pharm.web --hardware-bench
```

`COM3` is only an example; select the actual port and matching firmware. The HTTPS adapter continues to use the variables documented in RUNNING.md. Both interfaces accept `--data-dir` and `--catalog`. Desktop and browser simulation use the same default SQLite database in `%LOCALAPPDATA%/EPICS-Pharm/simulation`; hardware modes use `bench`. An outstanding operation blocks other interfaces/processes from starting another. One program should own a physical cabinet's serial connection at a time.

## Scanning and loading

Enter or scan a numeric package identifier, a GS1 Data Matrix, or a parenthesized GS1 label. Supported application identifiers are 01 (GTIN), 21 (serial), 17 (expiration) and 10 (lot). GS1 day 00 means the last day of its month. AIM scanner prefixes and FNC1 separators are accepted. The team's unseparated 01/21/17/10 ordering is accepted when there is a unique interpretation. Configure the scanner to preserve FNC1 separators for variable fields; unsupported or ambiguous formats are rejected.

GTIN-14 with `00` padding can map to its explicit UPC-A catalog alias, and UPC-A/GTIN-14 scans match catalog UPCs listed as EAN-13. A drug GTIN or UPC (`003` + NDC + valid check digit) matches the package NDC it carries. Package identity still requires an exact, unambiguous match; there is no NDC zero-padding or substring guess. A match also fills the unit type from the package description's outer container. Unknown or ambiguous scans retain their identity for manual entry, with the medication and unit filled only when every related catalog package agrees. The included FDA/openFDA catalog, `UI/db.json.xz`, remains the default. **Choose catalog** remembers a compatible full product-list/`results` JSON catalog, plain or compressed. The browser uploads a local copy; the desktop remembers its selected path.

Review medication identity, lot, actual expiration and counted unit. GS1 stock details come from the scanned package, rather than catalog listing dates. Each scanned serial can be recorded only once in current stock or the active loading session. Scanned boxes expiring within 31 days are not added. Manual entry still validates actual expiration and requires stock details.

In the browser, the first **Confirm and load box** requests access and stages its record. Scan and add further boxes of the same package and counted unit, then **Finish loading**. Different lots and expiration dates stay attached to their individual boxes. The desktop supports the same box records by scanning the requested units before placement. Manual quantities without box scans retain the repaired single-lot top-up validation.

Dispensing saves once every unit is scanned. Loading saves at **Finish loading** (browser) or **Done** (desktop), and emptying saves at **Done**, each pressed after closing the drawer; nothing senses closure, so that press is what tells the app to re-lock. A lock command is then requested, but its acknowledgement is not required to save inventory. No physical security confirmation is requested. A failed lock request is displayed without undoing the saved count.

## Dispensing, recovery, and records

Scan a prescription/package to find its drawer or use its **Dispense** button. Specify the count and verify each box. A GS1 serial must match a recorded, unverified, unexpired box. An ordinary product barcode can verify an unexpired unit of that package when no serial is supplied; scanning its serialized label provides exact box matching. Submitting an empty scan requests drawer access again if it has timed out. It does not automatically retry failed commands.

Cancelled, interrupted, or failed access remains visible for reconciliation after restarting either interface. Inspect the actual contents. For mixed lots or serial-numbered stock, select the recorded boxes physically present; a count alone cannot identify them. Anonymous single-lot stock saves the entered count directly, including increases, without another explanation prompt. A drawer with no recorded product still needs its contents identified before stock can be recorded; save zero only if it is empty. Existing aggregate SQLite stock is expanded into anonymous unit records on first use, with quantities and product metadata retained. Example JSON stock is not imported.

Both interfaces provide audit export, database backup, manual access with an optional reason, box-record details and earliest-expiration display. Expiration alerts appear within 31 days. The selected drawer shows its cached or bundled package label photo (click to enlarge). When none is saved, a bounded DailyMed lookup starts automatically in the background (once per package per session, or again with **Try again** after a failure) and caches the image outside the inventory transaction; the photo appears when it arrives. Failure to fetch a photo does not change stock or block other operations.

## Firmware and preserved team assets

`UI/LockLights.ino` and `UI/HardwareConfig.h` retain the repaired MAS/1 commissioning, configurable pulse/rest behavior and default disabled outputs. `arduino/LockLights/LockLights.ino` preserves the team's separate pressure-sensor, open-mode/LED and byte-echo protocol. A drawer it releases stays unlocked until its pressure sensor has read it as pulled out and then closed (it locks 2 seconds later), or for 10 seconds if it is never pulled out; the app's lock request still locks it at once. `OPEN_WAIT_MS`, `OUT_CONFIRM_MS` and `SENSOR_HOLD_MS` set these times. The solenoid is powered throughout, so keep them within the lock's rated on-time. Select the corresponding adapter explicitly. Team status reports output levels and open mode, not a measured closed/secured door. Inventory workflows select one compartment and serialize operations even though the team sketch can represent multiple open drawers. No firmware is automatically compiled, uploaded or electrically configured.

The cup/belt stepper demo remains in `arduino/cup_and_belt_guide_demo/` and is independent of inventory. The team's old screenshots, FDA conversion helpers and README were removed in the November 6, 2026 cleanup; they remain in Git history and in the team's original folder on GitHub. `deploy/pharm.service` is an optional Debian user-service template for the desktop in simulation; adjust its installation path and install it explicitly if needed. It was not installed or started as part of the merge.

The temporary source backups under `.merge-backup/` were removed during the October 1, 2026 cleanup. The app's inventory **Backup** function remains available; active inventory data is stored separately as documented in RUNNING.md.
