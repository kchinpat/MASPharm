> Hardware is being redesigned. Simulation needs no hardware decisions. See [current direction and historical reference](HARDWARE_REQUIREMENTS.md).

# Running the pharmacy drawer software

The September 30 combined version adds browser screens, GS1/serial/lot tracking, photos and a separate team-firmware adapter. [COMBINED_VERSION.md](COMBINED_VERSION.md) describes these current workflows and launch options. The older setup notes below remain useful for the repaired MAS/1 and HTTPS adapters. Stock can now contain multiple lots when loaded as individually recorded boxes; reconciliation then identifies the boxes remaining, rather than guessing their lot or serial from a count.

## Quick start on this Windows computer

1. Double-click **Launch Pharmacy Drawer.cmd** in the project folder.
2. The dashboard opens directly with four drawers. No password or account setup is required.
3. The banner says **SIMULATION**. No lock, light, serial port, or Pi is contacted.
4. Use **Load / top up** on a compartment. Enter synthetic details to try the workflow, including package identifier, lot, future actual expiration in `YYYY-MM-DD` format, and counted unit such as `bottle`.
5. Confirm details, quantity, simulated placement, and closure. Inventory saves without a lock acknowledgement or physical security confirmation. A lock command is requested afterward; failures are displayed without undoing the saved inventory.
6. Dispense by entering the same package identifier for each counted unit. Leading zeros matter. Cancelling after access or failing a scan leaves a visible reconciliation task.

Example for testing only: name `SYNTHETIC DEMO`, identifier `0123456789`, lot `DEMO`, expiration `2099-12-31`, unit `bottle`. These are not medication records.

The launcher accepts an optional project virtual environment, then looks for the local Codex Python runtime and Python on PATH. This cleaned project has no virtual environment; the existing Codex Python runtime on this computer supports the desktop. The supplied `runtime-dependencies.zip` provides the browser, USB and Pi API dependencies without extracting additional files. Keep it alongside `pharm/`. The desktop requires Python 3.10+ with Tcl/Tk and SQLite. If no suitable interpreter is found, install Python with Tcl/Tk from [python.org](https://www.python.org/downloads/windows/) and rerun. The launcher does not install software or change machine-wide execution policy. The console stays available for startup errors.

Direct alternatives, run from the project root:

```powershell
python -m pharm.app
python UI/main.py
```

F11 toggles fullscreen and Escape leaves it. The app begins in a resizable window. Simulation and bench mode still use separate databases.

## Data, accounts, and recovery

Default Windows simulation data lives in `%LOCALAPPDATA%\EPICS-Pharm\simulation`. Hardware bench data uses `%LOCALAPPDATA%\EPICS-Pharm\bench`. On other systems the default base is `~/.local/share`. Each directory contains `inventory.sqlite3` and `application.log`; SQLite may also create `-wal` and `-shm` files while running.

To select a different data directory:

```powershell
python -m pharm.app --data-dir C:\DrawerDemoData
```

Do not point simulation and hardware sessions at the same data directory. Do not place the active SQLite database on a network share or synchronize it while running. The current design supports one cabinet controlled by one desktop installation. Multiple processes sharing that same local database are prevented from starting overlapping inventory operations. Separate desktops with separate databases are not a supported multi-station deployment.

The laptop uses a shared password-free local session. Loading, dispensing, unloading, manual access, reconciliation, export, and backup are available to anyone using the app. There is no sign-in or user-management screen. Events use `local-workstation`, so they do not establish which staff member performed an action. Existing named accounts and their historical records are preserved but no longer gate laptop access. Machine-to-machine API authentication remains configured separately.

If access is interrupted, the durable pending record remains. Ordinary loading and dispensing are blocked. The operator must inspect the recorded compartment, verify the product and lot, remove any unidentified or unexpected stock, count the remaining units, enter a reason, and confirm closure using **Reconcile physical contents**. Reconciliation saves before the lock request and does not require a lock acknowledgement or physical security confirmation. A manual access action always requires a subsequent count.

Use **Backup** to create a new consistent SQLite backup filename. Use **Export audit** for a CSV copy of events. Neither backs up catalog data or deployment configuration. To restore, close all app instances, retain a copy of the entire current data directory for investigation, and restore the backup as `inventory.sqlite3` into a new data directory. Launch with `--data-dir` targeting that directory. Inspect pending operations and reconcile physical contents before further use. Do not replace a running database or mix old WAL files with a restored database.

The old `UI/medecine_data.json` and Pi copy remain untouched for reference. They are not automatically migrated because their unit, lot, identifier meaning, and actual stock expiration are unverified. Re-enter verified stock through the loading workflow when those facts are available.

## Catalog and barcode behavior

The September 26, 2026 official FDA NDC export is installed locally at `UI/db.json`, with 138,259 products and 256,495 package records. See [catalog source and verification](CATALOG_SOURCE.md). A copy of the code without this local data file still supports manual entry and displays a missing-catalog notice. Scan a numeric identifier and press Enter or select **Use scan / look up**. If no exact match exists, the scanned identifier is retained and the other fields are cleared for manual entry. A scan matching the drawer's existing package preserves its top-up details for review. Leading zeros are retained. Unsupported composite scans are rejected rather than guessed.

Use **Choose catalog** to select a compatible JSON file. A valid selection is remembered separately in the simulation or bench data directory; an invalid selection leaves the current catalog intact. Alternatively launch with `--catalog C:\path\catalog.json` for a session override. With no selection, `UI/db.json` remains the default. Supported shapes are a top-level product list or an object with a `results` list. Products may contain `generic_name`, `brand_name`, `labeler_name`, `packaging` entries with `package_ndc` and `description`, and `openfda.upc` lists. Catalog loading never sets a stock expiration date. The historical FDA product-index dictionary needs conversion with verified package mappings; it is not this format.

Lookup matches complete identifiers after removing separating hyphens, preserving leading zeros. UPC mapping only succeeds if it resolves to one unambiguous package. There is no substring matching, zero-padding guess, GS1 parser, or check-digit inference. Unsupported scanner formats must be specified and implemented before use. Until then, scan or enter the same supported package identifier associated with the loaded product.

Each drawer holds one product, lot, expiration, and counted unit. Top-ups must match all of these and the medication name. To change identity, unload and verify the compartment first. Expired stock cannot be loaded or dispensed; unloading remains possible. Month-only package expiration needs an agreed interpretation before entry; do not guess it from a catalog listing date.

Images are optional local reference assets. Automatic web scraping and network image downloads were removed from the loading path. No image is required to start or operate the current UI.

## Direct laptop-to-Arduino USB connection

This is an optional hardware adapter, not a settled redesign requirement. No Raspberry Pi, Wi-Fi, server, or API key is needed for USB. The supplied runtime bundle includes USB support. For a source-only copy without that bundle, install the USB dependency with the selected Python:

```powershell
python -m pip install -r requirements-usb.txt
```

After wiring and firmware are verified for a bench test, double-click **Launch USB Bench.cmd**. Select the Uno's COM port from the list, confirm bench preparation, and choose **Use selected port**. Refreshing the list does not open serial ports. The app does not contact the device merely because a port was selected; **Device status** or an access action opens it. Close Arduino IDE Serial Monitor or other software using that port first. Classic Nano boards using the same firmware are also supported.

The command-line equivalent is `python -m pharm.app --usb`. USB mode uses the separate `bench` data directory and displays the selected COM port. The simulation launcher is unchanged. Keep `runtime-dependencies.zip` in a copied project so another laptop can use the included USB dependency with its own Python installation.

USB opens at 9600 baud with two-second read/write timeouts and allows two seconds for an Uno/Nano reset after opening. It checks MAS/1 before each action. On a newly opened connection, a silent HELLO is tried up to three times on the same port to allow for startup. Explicit disabled/incompatible replies fail immediately. Actuator commands are never retried automatically. Normal app shutdown closes the serial connection. Do not probe the original legacy firmware: it handles unexpected command bytes unsafely. Install the repaired firmware under the hardware bench procedure first.

Automatic locking when pushed closed still depends on the actual lock or closure sensor. The timer and manual confirmation are not closure detection. These details must be established before actuator outputs are enabled.

### Uno firmware setup and command-0 timeouts

September 25 redesign update: the firmware no longer assumes either historical pin order or a 30-second release. Electrical settings are isolated in `UI/HardwareConfig.h`, with no selected profile. Simulation is ready for software development while the hardware design is open.

`Firmware did not acknowledge command 0: timeout` means the readiness probe received no reply. No drawer-open command was sent by this request. Dummy medication details do not affect the handshake. A COM port proves that Windows sees a serial adapter, not that the required sketch is installed. During the September 18 check, Windows listed `COM3 | USB-SERIAL CH340 (COM3)`; verify the port on your machine since its number can change.

An Uno resets when its serial port opens, as described in [Arduino's reset explanation](https://support.arduino.cc/hc/en-us/articles/4839084114460-If-your-board-runs-the-sketch-twice). The app now waits and tolerates initial silent readiness probes. A persistent timeout can still mean the wrong sketch, wrong port, or a board/serial connection problem.

To install the matching firmware on a classic ATmega328P Uno:

1. Close the pharmacy app and Arduino Serial Monitor. Disconnect actuator power while replacing unknown firmware.
2. Copy both `UI/LockLights.ino` and `UI/HardwareConfig.h` into a folder named `LockLights`, then open the sketch in Arduino IDE. Keep the header alongside it.
3. Install the **Adafruit NeoPixel** library in Library Manager. Select **Arduino Uno** under **Arduino AVR Boards** and select the board's COM port. An Uno R4 requires its actual board target instead.
4. Upload with the default `HARDWARE_COMMISSIONED=0` first. This build leaves lock/light pins undriven and replies `MAS/1 DISABLED`. That response confirms the protocol works; it intentionally does not allow drawer access.
5. For a future momentary-release lock design, configure `HardwareConfig.h`: four distinct pins D2 through D13, the driver's release level, a permitted pulse duration, and a minimum rest period after deactivation. Optional lighting requires a separate pin and valid segment boundaries. Set `HARDWARE_PROFILE_VERIFIED=1` and `HARDWARE_COMMISSIONED=1` only in the verified build. Missing, duplicated or conflicting settings fail compilation. The enabled build initializes inactive output levels on boot; electrical inactivity does not establish mechanical security. Other lock mechanisms require an appropriate firmware adapter.
6. Close Serial Monitor, restart **Launch USB Bench.cmd**, select the correct port, and use **Device status** before loading stock. A commissioned build should report `MAS/1 firmware ready`.

New connection/HELLO failures display **Arduino connection not ready**, cancel only the new unsent operation, and leave stock unchanged. A missing acknowledgment after a drawer command still requires reconciliation. Existing reconciliation records from the old app are preserved because they do not record whether a drawer command was sent. Once hardware communication works, use **Reconcile physical contents** to resolve those records from the observed contents.

## Optional legacy Raspberry Pi API

The following API deployment is retained for compatibility but is not needed for the confirmed direct-USB installation. Keep the repository's `pharm/` package alongside `rpi_folder_copy/`, because both adapters now share one serial controller.

These steps are preparation for a controlled bench test. Do not connect the repaired controller to legacy firmware. The old firmware handles unknown bytes unsafely, including a version probe. Flash and verify the new firmware under the hardware team's bench procedure first.

1. See HARDWARE_REQUIREMENTS.md for the redesign direction. The existing four-compartment application can run in simulation regardless of board choice. The optional firmware needs a configured electrical profile before outputs are enabled; timers do not detect closure.
2. The header `UI/HardwareConfig.h` defaults to `HARDWARE_COMMISSIONED=0`. The firmware reports `MAS/1 DISABLED` and does not drive actuator/LED pins. The API rejects access to a disabled or incompatible controller. Enabling outputs also requires a valid verified profile.
3. On the Pi, run `sh rpi_folder_copy/setup.sh` to prepare its venv and dependencies. The script no longer generates Python source, creates credentials, installs a service, or starts one.
4. Set `MAS_API_KEY` to a newly generated secret of at least 32 characters outside source control. Rotate any key previously deployed from the original snapshot. No Git history exists in this downloaded directory, so removal from upstream history and rotation on devices still require the owning repository/device.
5. Set `MAS_SERIAL_PORT` if it is not `/dev/serial0`. Verify the service user can access it and that the UART is not occupied by the login console. The serial module does not open the port on import.
6. Run the maintained server from the Pi folder with `.venv/bin/python secure_api.py`. `secure_api_2.py` is only a compatibility wrapper around the same application factory.
7. The Waitress server binds to `127.0.0.1:5000`. Provide an HTTPS reverse proxy with a trusted certificate, limited network access, and no unintended public exposure. Provisioning the proxy, Pi service user, and unit file depends on the actual Pi deployment. Run one server process so it owns one serial command queue.
8. On the desktop, configure `MAS_API_URL=https://your-pi-host`, `MAS_API_KEY`, and optionally `MAS_CA_FILE` for a private CA certificate. Start `python -m pharm.app --hardware-bench`. The ordinary double-click launcher always chooses simulation.

The client verifies TLS, has a bounded request timeout, and never automatically retries a hardware action. All requests use `X-API-Key`. API status checks firmware readiness, but no supplied sensor measures physical lock/door state. A successful response means the firmware acknowledged a command; the UI requires an operator's closure and security confirmations.

Supported routes:

| Route | Body | Effect |
| --- | --- | --- |
| `GET /status` | None | Check serial protocol and commissioning readiness. |
| `POST /open_drawer` | `{"drawer": 1}` | Select one drawer, securing the other three first. |
| `POST /lock_drawer` | `{}` | Request all outputs locked and lights off. |
| `POST /unlock_cabinet_lock` | `{"box": 1}` | Same isolated selection behavior as opening. |
| `POST /lock_cabinet_lock` | `{"box": 1}` | Request the selected compartment locked. |
| `POST /light` | `{"box": 1}` | Illuminate a compartment. |
| `POST /unlock` | `{}` | Returns 409: all-compartment emergency release is not enabled. |

Missing/wrong credentials return 401, invalid bodies and compartment values return 400, oversized bodies return 413, and serial/acknowledgement failures return 503. API responses explicitly report physical state as `unmeasured`.

### MAS/1 firmware protocol

Serial is 9600 baud, 8N1, raw bytes. HELLO byte 0 must return `MAS/1 READY` before any action. A disabled build returns `MAS/1 DISABLED`. Other valid commands return `MAS/1 ACK <decimal-command>`. After bounded startup HELLO attempts, timeout, missing acknowledgement, or unexpected response fails the request and closes the serial connection. The next explicit request may reopen it; uncertain inventory operations must be reconciled before ordinary access.

| Bytes | Meaning |
| --- | --- |
| 0 | Protocol/commissioning probe |
| 1-4 | Select and unlock one compartment, securing others first |
| 5-8 | Lock compartment 1-4 |
| 9 | Rejected; there is no shared outer drawer |
| 10 | Lock all |
| 11-14 | Light 1-4 on |
| 15-18 | Light 1-4 off |
| 19 | Lock all |
| 20-23 | Explicit select/access compartment 1-4, used by the application |

Unknown bytes cause no output changes. No ASCII digit conversion remains. Release commands start the configured pulse and acknowledge its acceptance, not physical opening. Each pulse ends independently of the laptop, and its drawer then rests for the configured interval. Access during a pulse or that drawer's rest interval returns `MAS/1 ERR BUSY` without extending the pulse. A lock command immediately ends the corresponding pulse. Optional lights have a separate timeout; light requests return `MAS/1 ERR UNSUPPORTED` if lighting is disabled. No hardware pin map is selected by default. Actual security during power loss depends on the lock hardware.

## Development checks

From the project root:

```powershell
$taskPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython -B -m unittest discover -s tests -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\launch.ps1 -SmokeTest -DataDir (Join-Path $env:TEMP 'EPICS-Pharm-smoke')
```

These commands use the existing Python runtime on this computer. On another computer, use its Python 3.10+ interpreter with Tcl/Tk and SQLite. The smoke test opens a password-free local session, renders the four-drawer dashboard and loading form, then exits without contacting hardware. It needs a normal Windows desktop session. The sandbox used for code inspection cannot initialize Tcl/Tk on this machine; the normal Windows execution test passed.

For firmware compilation, use the [official Arduino CLI](https://docs.arduino.cc/arduino-cli/installation), the board's actual platform, and Adafruit NeoPixel. Copy the sketch and `HardwareConfig.h` to a temporary `LockLights` folder for compilation. Never upload during an automated software test. `tests/test_firmware.py` also compiles and executes the actual sketch against simulated pins, serial and time when `g++` or a configured Visual Studio `cl` is on PATH. Those test profiles are synthetic and must not be uploaded.

See [software changes and validation](SOFTWARE_FIXES.md) for what was checked and what still depends on hardware requirements.
