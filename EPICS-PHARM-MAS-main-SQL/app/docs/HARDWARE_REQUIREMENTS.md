# Hardware redesign and historical reference

Updated September 25, 2026 from the user's answers, supplied wiring image, and historical archive review.

## Current direction

The user clarified that this is a redesign and no hardware choice is certain. The descriptions below are historical observations, not requirements for the new build. Software work proceeds in simulation without waiting for hardware selection.

September 26 catalog update: the latest official FDA NDC JSON export is now installed locally. Earlier missing-catalog statements below describe the original archives. See [catalog source and verification](CATALOG_SOURCE.md).

The desktop inventory and catalog workflows depend on the hardware adapter's `open`, `lock`, `status`, and `close` interface. Simulation, direct USB, and HTTPS remain separate adapters. The present UI and inventory model retain four compartments; changing that count is a separate schema and UI change.

`UI/HardwareConfig.h` now isolates electrical configuration: drawer pins, release polarity, pulse time, minimum rest time, and optional NeoPixel layout. Defaults are unset, with outputs disabled. Enabling outputs with an incomplete or conflicting profile fails compilation. The current Arduino adapter implements momentary release; a different mechanism or physical sensors can be implemented behind the same desktop interface once selected. Neither historical pin map is selected by default.

Release pulses end independently of UI completion, and repeated access requests cannot extend an active pulse or bypass that drawer's rest period. Lock commands stop a release pulse. These are electrical actions and do not prove that a drawer latched.

## Previously observed installation

- Controller observed September 18: Arduino Uno, corrected by the user during the USB-timeout report. The bootloader returned ATmega328P signature `0x1e950f`. Exact board revision remains unconfirmed. That day's MAS/1 firmware was uploaded with `HARDWARE_COMMISSIONED=0` and its `MAS/1 DISABLED` reply verified. The September 25 redesign firmware has not been uploaded.
- Physical arrangement: four separate drawers, with no shared outer drawer.
- UI: runs on a laptop.
- Access: no password prompt in the laptop software. Anyone with access to the running laptop app can use its functions. Audit records identify the shared workstation, not an authenticated person.
- Closing: each drawer must lock automatically when pushed closed. The user's initial wording was clarified explicitly.
- Reference wiring supplied September 25: four solenoid locks labeled 12 V, an eight-channel relay module, a 12 V 5 A supply, and a 5 V 2 A supply. Exact lock and relay models, installed wiring, coil ratings, and closure behavior remain unverified. Scanner is tentatively a NETUM NT-1228BC. The real catalog is still missing.
- Connection: laptop directly to Arduino Uno over USB, confirmed by the user. The user confirmed that only USB is connected, with no drawer locks attached. No Raspberry Pi, network API, or API key is required for this installation. The CH340 adapter is at `COM3`; firmware upload and a 9600-baud MAS/1 handshake have now succeeded on that port.

## Software behavior now

The launcher opens the dashboard directly, including with an existing database. Existing named accounts, stock, and audit records are preserved. Local-session audit entries document the password-free access policy. API credentials remain machine connection settings, not a user password prompt.

The interface uses Drawer 1 through Drawer 4. The firmware has no fifth/main drawer output. Byte 9, formerly main-only release, is rejected. Firmware pins are now unset and outputs remain disabled by default.

Automatic locking on actual closure is not implemented or claimed without a way to establish how the locks latch or how closure is sensed. The former 30-second release timeout has been removed. The remaining 30-second default controls optional lighting only. The simulator still asks for simulated closure confirmation.

## Information for future hardware integration, not a software prerequisite

1. Supply the exact lock and relay module model numbers or product links. Verify coil current, permitted pulse duration, relay input polarity, contact wiring, and flyback protection against the installed hardware.
2. Confirm which part of the reference drawing matches the current cabinet. Its lock controller looks like a Nano, whereas the previously connected board was identified as an ATmega328P Uno. The image also includes separate stepper arrangements. Trace drawer-to-pin connections before selecting either historical pin map.
3. Confirm whether the four pressure sensors in the archived code are physically installed and whether the locks mechanically latch when pushed closed. Pressure readings in that code trigger another release pulse; they do not prove closure or a secured latch.
4. Provide a representative package barcode photo or exact scanner output before finalizing scanner support. The tentative scanner supports linear barcodes, not the old application's Data Matrix workflow.

Medication catalog and scanner integration can follow the empty-drawer bench test. No lock should be actuated until its wiring/power behavior is verified.

## September 25 archive and diagram findings

Source: user-supplied `PHARM-MAS-mainOLD.zip`, containing `PHARM-MAS-main/EPICS-PHARM-MAS-main.zip`. The inner archive includes a historical application and a nested duplicate. Files were read as historical evidence; no archived scripts were executed and no firmware was uploaded.

The historical `EPICS-PHARM-MAS-main/UI/LockLights.ino` differed materially from the maintained firmware at the time of initial inspection, before the redesign fixes:

| Item | Supplied historical sketch | Maintained sketch before redesign fixes |
| --- | --- | --- |
| Drawer 1, 2, 3, 4 pins | D8, D10, D6, D7 | D10, D8, D7, D6 |
| Release signal | LOW for 500 ms, then HIGH | LOW until lock request or 30-second timeout |
| Pressure inputs, drawers 1 to 4 | A3, A2, A1, A0 | Not implemented |
| Pressure behavior | Reading below 600 repeats a 2-second release pulse for the selected drawer | Not implemented |
| LED data | D4, 91 pixels | D4, 91 pixels |
| Serial replies | Echoes command byte | MAS/1 readiness and acknowledgements |

The old sketch explicitly describes its short release pulse as protection against overheating. Neither its pulse lengths nor the former 30-second timeout establish a permissible coil duty cycle. The redesign fixes replace both assumptions with an explicit, initially unset pulse/rest configuration. The old pressure loop can repeat pulses continuously while its threshold condition persists, so it was not copied as verified closure handling.

The drawing labels four 12 V solenoids and shows relay control, but is a collection of several circuit layouts. Small terminal labels and exact relay contacts cannot be reliably verified from it. Supply labels in this reference do not establish the actual installed supplies or their suitability for the loads.

The archive also includes a GS1 parser and examples with GTIN, serial number, expiration, and lot. Its README describes scanning 2D Data Matrix symbols. These are historical examples, not proof that the tentative scanner can read them. The parser guesses variable-field boundaries from digit pairs instead of reliably handling separators and is not suitable for direct adoption.

NETUM's [NT-1228BC specifications](https://support.netum.net/hc/en-us/articles/43479146308891-NT-1228BC-Barcode-Scanner-Complete-Specifications) list a linear CCD engine with UPC/EAN, Code 128 and GS1-128 support. The model is a 1D scanner and does not read Data Matrix or QR symbols. Its [official setup guide](https://doc3.netum.net/NT-1228BC/en/) documents keyboard input and connection settings. Keyboard input is a candidate for the current numeric identifier fields, subject to an actual scan test. If Data Matrix scanning is required, choose a scanner explicitly supporting that symbology and implement validated parsing in the application.

The historical catalog loader expects `fda_product_db_indexed.json`. That file, `fda_product_db.json`, and the conversion source `product.csv` are absent from the supplied archive. Conversion scripts and example inventory are present. The historical product-index format also differs from the maintained catalog format, so recovering the JSON alone would not make it a drop-in replacement.

## Verification of this update

46 Python regression tests passed, including password-free access with existing accounts and reconciliation of an interrupted named-user operation. The actual Windows launcher rendered the password-free dashboard and loading form successfully.

Both disabled and compile-only enabled firmware configurations compiled for `arduino:avr:nano:cpu=atmega328` using AVR core 1.8.6 and NeoPixel 1.12.5. This is a classic Nano compatibility check, not identification of the user's exact board. No firmware was uploaded and no physical output was actuated. The maintained source still defaults to disabled outputs.

Direct USB update: 51 tests passed, including lazy serial opening, Windows serial parameters, the Nano reset wait, disabled firmware, missing acknowledgement, port cleanup, and read-only enumeration. The laptop and optional legacy Pi server use the same controller implementation in `pharm/serial_controller.py`.
