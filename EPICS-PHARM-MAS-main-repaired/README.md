# EPICS-PHARM-MAS

Pharmacy drawer software for an ongoing hardware redesign, with a four-compartment desktop interface, simulation, and replaceable USB or HTTPS hardware adapters.

Double-click **Launch Pharmacy Drawer.cmd** to open the four-drawer desktop app in **simulation mode**. No password, account setup, network access, or Pi is required for simulation. Actions are logged under the shared `local-workstation` identity.

Read the [current setup and operating guide](docs/RUNNING.md) and [software changes and verification](docs/SOFTWARE_FIXES.md). The [original review](PROJECT_GUIDE.md) documents the earlier snapshot.

The maintained application is in `pharm/`. Inventory now uses SQLite with pending operations, reconciliation, operator accounts, and an audit trail. Existing example JSON files are preserved but are not imported as real stock. Catalog lookup is optional; manual entry requires package identity, lot, actual expiration, and the counted unit.

Hardware choices are open. **Launch USB Bench.cmd** provides an optional COM-port adapter for compatible Arduino firmware, with no Pi or API key. Install `requirements-usb.txt` for USB support. Firmware pin assignments, release polarity, pulse duration, rest period, and optional lights live in `UI/HardwareConfig.h`; its default profile is unconfigured and outputs are disabled. The current firmware adapter supports momentary release, not every possible lock mechanism. No hardware is required to develop or use simulation.

On the loading screen, scan a numeric package identifier and press Enter. Without a catalog match, the identifier is kept for manual entry. **Choose catalog** selects and remembers a compatible JSON catalog. No specific scanner brand is required; keyboard input from a scanner follows the same path as typing. Composite GS1/Data Matrix parsing is not implemented.

The local catalog has been updated to the **September 26, 2026 FDA NDC release**, with 138,259 products and 256,495 package records. Restart the app to load it. See [catalog source and verification](docs/CATALOG_SOURCE.md).
