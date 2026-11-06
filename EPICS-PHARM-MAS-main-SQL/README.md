# EPICS Pharmacy Drawer

Pharmacy cabinet software with desktop and browser interfaces, GS1 scanning, individual box/lot/serial records, simulation, and replaceable USB or HTTPS hardware adapters.

## Start

Double-click a launcher in this folder.

| Launcher | Opens |
| --- | --- |
| **Pharmacy Drawer** | The four-drawer desktop app in **simulation**. No password, account setup, network access or Pi is needed. |
| **Browser Cabinet** | The same cabinet in your browser at `http://127.0.0.1:8000`, in simulation. Its window runs the local server; close it to stop. |
| **USB Bench** | The desktop app connected by USB to an Arduino running the repaired MAS/1 firmware, `app/UI/LockLights.ino`. |
| **Team USB Bench** | The desktop app connected by USB to the team's pressure-sensor/byte-echo firmware, `app/arduino/LockLights/`. |

The launchers find Python 3.10 or later with Tcl/Tk and SQLite on their own; on this computer they use the bundled Python outside the project folder. Elsewhere, install Python from [python.org](https://www.python.org/downloads/windows/). Desktop and browser simulation share one inventory, and the USB benches use a separate one. Actions are logged under the shared `local-workstation` identity.

## Using it

Dispensing saves once every unit is scanned; loading and emptying save when you press **Done** after closing the drawer. Interrupted access requires reconciliation. The dashboard opens in UI two, where every drawer stays in view; **Menu** switches to the legacy UI and between light and dark themes.

On the loading screen, scan a numeric package identifier or GS1 Data Matrix and press Enter. GS1 AIs 01 (GTIN), 21 (serial), 17 (actual expiration) and 10 (lot) are supported, including FNC1 separators, parenthesized labels and the team's unseparated serial/expiration/lot pattern when unambiguous. A scan fills the medication name and unit type (the package's outer container, such as bottle or carton) from the catalog. Drug UPC-A, EAN-13 and GTIN-14 barcodes are matched through the NDC they carry. Without an exact package match, the scanned identity is kept and the medication and unit are still filled when every related catalog package agrees; review them against the label. Manual entry requires package identity, lot, actual expiration and the counted unit. No specific scanner brand is required; keyboard input from a scanner follows the same path as typing.

Individual box records support multiple lots of the same product, duplicate serial rejection, exact serial verification and earliest-expiration display. Each drawer shows its package label photo when one is saved; click it to enlarge. A missing one downloads from DailyMed in the background and is cached; photo lookup never changes inventory.

The catalog is the **September 26, 2026 FDA NDC release**, 138,259 products and 256,495 package records, kept as a verified 3.3 MB compact file. **Choose catalog** (in **Menu**) selects and remembers another compatible JSON catalog. See [catalog source and verification](app/docs/CATALOG_SOURCE.md).

## Hardware

No hardware is required for simulation. Firmware pin assignments, release polarity, pulse duration, rest period and optional lights live in `app/UI/HardwareConfig.h`; its default profile is unconfigured and outputs are disabled. The two USB benches use distinct firmware profiles, and no firmware is uploaded automatically. The current firmware adapter supports momentary release, not every possible lock mechanism. An optional Raspberry Pi HTTPS API is in `app/rpi_folder_copy/`.

## Folder layout

```
Pharmacy Drawer.exe        Browser Cabinet.exe        USB Bench.exe        Team USB Bench.exe
app/
  pharm/                   the application: workflows, SQLite inventory, desktop and browser UIs
  UI/                      theme, browser page, FDA catalog, MAS/1 firmware
  runtime-dependencies.zip Flask and pyserial, imported directly; keep it with the app
  arduino/                 team firmware and the cup/belt demo
  rpi_folder_copy/         optional Raspberry Pi HTTPS API
  docs/                    guides
  tests/  tools/  launcher/  deploy/
```

Inventory uses SQLite with pending operations, reconciliation, an audit trail, consistent backups and optional backend account support, stored in `%LOCALAPPDATA%\EPICS-Pharm`, outside this folder.

## Documentation

- [Setup and operating guide](app/docs/RUNNING.md), including development checks and rebuilding the launchers
- [Combined-version workflows and launch options](app/docs/COMBINED_VERSION.md)
- [Hardware requirements](app/docs/HARDWARE_REQUIREMENTS.md)
- [Software changes and verification](app/docs/SOFTWARE_FIXES.md)

## History

This repository previously also held the original Tkinter prototype (`EPICS-PHARM-MAS-main/`), its review README and a Word user guide. They were replaced by this version and remain available in the git history.
