# EPICS-PHARM-MAS

Combined pharmacy cabinet software with desktop and browser interfaces, GS1 scanning, individual box/lot/serial records, simulation, and replaceable USB or HTTPS hardware adapters.

The team's September 30 snapshot is integrated with the repaired SQLite workflows. Start **Launch Pharmacy Drawer.cmd** for the desktop or **Launch Browser Cabinet.cmd** for the browser. Both default to simulation and share its inventory. Loading, dispensing and emptying finalize stock only after confirmations; interrupted access requires reconciliation. See [combined-version instructions](docs/COMBINED_VERSION.md).

Double-click **Launch Simulation.cmd** to open the four-drawer desktop app in **simulation mode** with no console window left open. **Launch Pharmacy Drawer.cmd** opens the same app but keeps its console visible for startup diagnostics. No password, account setup, network access, or Pi is required for simulation. Actions are logged under the shared `local-workstation` identity.

Read the [current setup and operating guide](docs/RUNNING.md) and [software changes and verification](docs/SOFTWARE_FIXES.md). The [original review](PROJECT_GUIDE.md) documents the earlier snapshot.

The maintained application is in `pharm/`. Inventory uses SQLite with pending operations, reconciliation, an audit trail, consistent backups, and optional account support in the backend. The default workstation session remains password-free. Existing example JSON files are preserved but are not imported as real stock. Catalog lookup is optional; manual entry requires package identity, lot, actual expiration, and the counted unit. Individual box records support multiple lots of the same product, duplicate serial rejection, exact serial verification and earliest-expiration display.

Hardware choices are open. **Launch USB Bench.cmd** provides an optional COM-port adapter for compatible Arduino firmware, with no Pi or API key. Install `requirements-usb.txt` for USB support. Firmware pin assignments, release polarity, pulse duration, rest period, and optional lights live in `UI/HardwareConfig.h`; its default profile is unconfigured and outputs are disabled. The current firmware adapter supports momentary release, not every possible lock mechanism. No hardware is required to develop or use simulation.

On the loading screen, scan a numeric package identifier or GS1 Data Matrix and press Enter. GS1 AIs 01 (GTIN), 21 (serial), 17 (actual expiration), and 10 (lot) are supported, including FNC1 separators, parenthesized labels and the team's unseparated serial/expiration/lot pattern when unambiguous. Without a catalog match, the scanned identity is kept for manual entry. **Choose catalog** (in **Menu**) selects and remembers a compatible JSON catalog. No specific scanner brand is required; keyboard input from a scanner follows the same path as typing.

Each drawer shows its package label photo when one is saved; click it to enlarge. **Download photo** fetches a missing one from DailyMed and caches it; photo lookup never changes inventory. Browser photos need no extra image library. Install `requirements-photos.txt` only for optional JPEG display on the desktop. The included `runtime-dependencies.zip` supplies Flask, USB serial support and the Pi API packages without a local virtual environment. Keep this runtime bundle with the project. The launchers use an available Python installation with Tcl/Tk and SQLite; on this computer they use the existing bundled Python outside the project folder.

**Launch USB Bench.cmd** uses repaired MAS/1 firmware. **Launch Team USB Bench.cmd** explicitly uses the team's pressure-sensor/byte-echo firmware in `arduino/LockLights/`. Both use the maintained inventory workflows. These firmware profiles are distinct and no firmware is automatically uploaded. The cup/belt demo, FDA conversion utilities, screenshots, and optional Debian service template are also preserved.

The local catalog has been updated to the **September 26, 2026 FDA NDC release**, with 138,259 products and 256,495 package records. Restart the app to load it. See [catalog source and verification](docs/CATALOG_SOURCE.md).
