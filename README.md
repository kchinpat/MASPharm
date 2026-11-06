# EPICS Pharmacy Drawer

Pharmacy cabinet software with desktop and browser interfaces, GS1 scanning, individual box/lot/serial records, simulation, and replaceable USB or HTTPS hardware adapters.

The project is in [`EPICS-PHARM-MAS-main-SQL/`](EPICS-PHARM-MAS-main-SQL/). Its [README](EPICS-PHARM-MAS-main-SQL/README.md) has the full guide.

## Start

Open `EPICS-PHARM-MAS-main-SQL/` and double-click a launcher.

| Launcher | Opens |
| --- | --- |
| **Pharmacy Drawer** | The four-drawer desktop app in simulation. No password, account, network or Pi needed. |
| **Browser Cabinet** | The same cabinet in your browser at `http://127.0.0.1:8000`, in simulation. |
| **USB Bench** | The desktop app connected by USB to an Arduino running the MAS/1 firmware. |
| **Team USB Bench** | The desktop app connected by USB to the team's pressure-sensor firmware. |

The launchers need Python 3.10 or later with Tcl/Tk and SQLite, from [python.org](https://www.python.org/downloads/windows/).

## Contents

```
EPICS-PHARM-MAS-main-SQL/
  *.exe                    launchers
  app/
    pharm/                 the application: workflows, SQLite inventory, desktop and browser UIs
    UI/                    theme, browser page, FDA catalog, MAS/1 firmware
    arduino/               team firmware and the cup/belt demo
    rpi_folder_copy/       optional Raspberry Pi HTTPS API
    docs/                  guides
    tests/  tools/  launcher/  deploy/
```

## Documentation

- [Setup and operating guide](EPICS-PHARM-MAS-main-SQL/app/docs/RUNNING.md)
- [Combined-version workflows and launch options](EPICS-PHARM-MAS-main-SQL/app/docs/COMBINED_VERSION.md)
- [Hardware requirements](EPICS-PHARM-MAS-main-SQL/app/docs/HARDWARE_REQUIREMENTS.md)
- [Catalog source and verification](EPICS-PHARM-MAS-main-SQL/app/docs/CATALOG_SOURCE.md)
- [Software changes and verification](EPICS-PHARM-MAS-main-SQL/app/docs/SOFTWARE_FIXES.md)
