# Combined version, September 30, 2026

The repaired directory is the maintained combined application. It includes the team's browser design, GS1 scanning, individual box tracking, photos and pressure-sensor firmware support, alongside transactional inventory, recovery, audit export, backups, manual entry and exact catalog matching.

## Start the interfaces

- **Launch Simulation.cmd** opens the desktop in simulation without leaving a console window open.
- **Launch Pharmacy Drawer.cmd** opens the desktop in simulation and keeps its console for diagnostics.
- **Launch Browser Cabinet.cmd** starts the local browser server and opens `http://127.0.0.1:8000`. Keep its console open; closing the server stops the browser interface.
- **Launch USB Bench.cmd** selects a port for repaired MAS/1 firmware.
- **Launch Team USB Bench.cmd** selects a port for the team's pressure-sensor/byte-echo firmware.

The included `runtime-dependencies.zip` supplies the browser, USB and Pi API dependencies without a local virtual environment. It retains the package sources, licenses and metadata, and Python imports it directly without extraction. Keep it with the project. Python 3.10+ with Tcl/Tk and SQLite is still required. For a source-only copy without the bundle, install the optional dependencies with the same Python used to launch the app:

```powershell
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-usb.txt
# Optional JPEG display in the desktop:
python -m pip install -r requirements-photos.txt
```

From the project root:

```powershell
python -m pharm.app
python -m pharm.web
python UI/main.py
python UI/web_server.py --no-hardware
python -m pharm.web --usb-port COM3
python -m pharm.web --team-usb-port COM3
python -m pharm.web --hardware-bench
```

`COM3` is only an example; select the actual port and matching firmware. The HTTPS adapter continues to use the variables documented in RUNNING.md. Both interfaces accept `--data-dir` and `--catalog`. Desktop and browser simulation use the same default SQLite database in `%LOCALAPPDATA%/EPICS-Pharm/simulation`; hardware modes use `bench`. An outstanding operation blocks other interfaces/processes from starting another. One program should own a physical cabinet's serial connection at a time.

## Scanning and loading

Enter or scan a numeric package identifier, a GS1 Data Matrix, or a parenthesized GS1 label. Supported application identifiers are 01 (GTIN), 21 (serial), 17 (expiration) and 10 (lot). GS1 day 00 means the last day of its month. AIM scanner prefixes and FNC1 separators are accepted. The team's unseparated 01/21/17/10 ordering is accepted when there is a unique interpretation. Configure the scanner to preserve FNC1 separators for variable fields; unsupported or ambiguous formats are rejected.

GTIN-14 with `00` padding can map to its explicit UPC-A catalog alias. The catalog still requires exact, unambiguous package matches and does not guess NDC zero-padding or substring matches. Unknown scans retain their identity for manual entry. The included FDA/openFDA `UI/db.json` remains the default catalog. **Choose catalog** remembers a compatible full product-list/`results` JSON catalog. The browser uploads a local copy; the desktop remembers its selected path. The historical FDA `tools/` scripts produce the team's older product index, which is not a package catalog for the maintained app.

Review medication identity, lot, actual expiration and counted unit. GS1 stock details come from the scanned package, rather than catalog listing dates. Each scanned serial can be recorded only once in current stock or the active loading session. Scanned boxes expiring within 31 days are not added. Manual entry still validates actual expiration and requires stock details.

In the browser, the first **Confirm and load box** requests access and stages its record. Scan and add further boxes of the same package and counted unit, then **Finish loading**. Different lots and expiration dates stay attached to their individual boxes. The desktop supports the same box records by scanning the requested units before placement. Manual quantities without box scans retain the repaired single-lot top-up validation.

Inventory changes after placement/removal and closure confirmation. A lock command is then requested, but its acknowledgement is not required to save inventory. No physical security confirmation is requested. A failed lock request is displayed without undoing the saved count.

## Dispensing, recovery, and records

Scan a prescription/package to find its drawer or use its **Dispense** button. Specify the count and verify each box. A GS1 serial must match a recorded, unverified, unexpired box. An ordinary product barcode can verify an unexpired unit of that package when no serial is supplied; scanning its serialized label provides exact box matching. Submitting an empty scan offers one explicit reopening request if access has timed out. It does not automatically retry failed commands.

Cancelled, interrupted, or failed access remains visible for reconciliation after restarting either interface. Inspect the actual contents. For mixed lots or serial-numbered stock, select the recorded boxes physically present; a count alone cannot identify them. Remove unidentified stock. Record the reason, confirm closure and security, then save. Anonymous single-lot stock can still be reconciled by its observed count. Existing aggregate SQLite stock is expanded into anonymous unit records on first use, with quantities and product metadata retained. Example JSON stock is not imported.

Both interfaces provide audit export, database backup, manual access with a reason, box-record details and earliest-expiration display. Expiration alerts appear within 31 days. The selected drawer shows its cached or bundled package label photo (click to enlarge). When none is saved, **Download photo** offers an optional bounded DailyMed lookup, which caches the image outside the inventory transaction. Failure to fetch a photo does not change stock or block other operations.

## Firmware and preserved team assets

`UI/LockLights.ino` and `UI/HardwareConfig.h` retain the repaired MAS/1 commissioning, configurable pulse/rest behavior and default disabled outputs. `arduino/LockLights/LockLights.ino` preserves the team's separate pressure-sensor, open-mode/LED and byte-echo protocol. Select the corresponding adapter explicitly. Team status reports output levels and open mode, not a measured closed/secured door. Inventory workflows select one compartment and serialize operations even though the team sketch can represent multiple open drawers. No firmware is automatically compiled, uploaded or electrically configured.

The cup/belt stepper demo remains in `arduino/cup_and_belt_guide_demo/` and is independent of inventory. Screenshots, FDA conversion helpers and the team README are preserved. `deploy/pharm.service` is an optional Debian user-service template for the desktop in simulation; adjust its installation path and install it explicitly if needed. It was not installed or started as part of the merge.

The temporary source backups under `.merge-backup/` were removed during the October 1, 2026 cleanup. The app's inventory **Backup** function remains available; active inventory data is stored separately as documented in RUNNING.md.
