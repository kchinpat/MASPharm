# EPICS PHARM MAS (historical team snapshot)

This document records the supplied team version before integration. Use [COMBINED_VERSION.md](COMBINED_VERSION.md) for the maintained entry points, SQLite inventory workflows and firmware selection.

This is the documentation on the user interface and arduino programs for the EPICS MAS software

The laptop used for this project is located in the drawer.
It runs on Debian Linux.

To develop this software, it is recommended that you either have WSL installed on your windows machine, or have linux running on your own laptop.
Or, simply do all of your development on the laptop that already has debian linux installed on it.

## How to run

Have python 3 installed on your system

Create a virtual environment with the necessary python packages to run this program

`python3 -m venv .venv`

On debian linux (like the laptop is)
`source .venv/bin/activate`

If on Windows, I believe it is `.venv/scripts/Activate.ps1`

If this is the first time running this, 

`cd EPICS-PHARM-MAS`

`pip install -r requirements.txt`

`cd UI`

`python main.py`

And now the user interface should be running

![Dispensing Screen](./readme-imgs/dispensing_screen.png)

## Project structure

```text
UI/                   The pharmacy app. Run main.py from inside this folder.
  images/             Downloaded medication photos (created at runtime, not committed)
arduino/
  LockLights/                 Drawer locks, LEDs, and pressure sensors (used by the app)
  cup_and_belt_guide_demo/    Cup and belt guide stepper demo (not connected to the app)
tools/                Scripts for building the FDA database and testing NDC lookups
deploy/pharm.service  systemd service that starts the app on the laptop
readme-imgs/          Screenshots used in this readme
```

## Rebuilding the FDA database

`UI/fda_product_db_indexed.json` is not committed because it is large.
To rebuild it:

1. Download `product.txt` from the [FDA NDC directory](https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory), rename it to `product.csv`, and place it in `tools/`
2. `python tools/convert_nda_db_to_json.py` (creates `UI/fda_product_db.json`)
3. `python tools/convert_nda_db_to_optimized_json.py` (creates `UI/fda_product_db_indexed.json`)

To check that barcode lookups work: `python tools/test_querying_ndc_barcode.py`

## Files

### `medecine_data.json`

Here's an example of what this file may look like:

```json
[
    {
        "cabinet_number": 1,
        "fill_status": true,
        "ndc": "359651029886",
        "quantity": 2,
        "current_stored_medecine": {
            "PRODUCTID": "59651-029_7bc1835a-cc34-4b65-a6b5-f290aee806b4",
            "PRODUCTNDC": "59651-029",
            "PRODUCTTYPENAME": "HUMAN PRESCRIPTION DRUG",
            "PROPRIETARYNAME": "Lo-Zumandimine",
            "PROPRIETARYNAMESUFFIX": "",
            "NONPROPRIETARYNAME": "Drospirenone and Ethinyl Estradiol",
            "DOSAGEFORMNAME": "KIT",
            "ROUTENAME": "",
            "STARTMARKETINGDATE": "20180227",
            "ENDMARKETINGDATE": "",
            "MARKETINGCATEGORYNAME": "ANDA",
            "APPLICATIONNUMBER": "ANDA209632",
            "LABELERNAME": "Aurobindo Pharma Limited",
            "SUBSTANCENAME": "",
            "ACTIVE_NUMERATOR_STRENGTH": "",
            "ACTIVE_INGRED_UNIT": "",
            "PHARM_CLASSES": "",
            "DEASCHEDULE": "",
            "NDC_EXCLUDE_FLAG": "N",
            "LISTING_RECORD_CERTIFIED_THROUGH": "20261231",
            "gtin": "00359651029886",
            "sn": "7AYN7S3AXN4YG6K",
            "exp": "280430",
            "lot": "CYAZES25035A",
            "BARCODENDC": "0100359651029886217AYN7S3AXN4YG6K1728043010CYAZES25035A"
        },
        "stored_medications": [
            {
                "orignal_scan": "0100359651029886217AYN7S3AXN4YG6K1728043010CYAZES25035A",
                "ndc": "359651029886",
                "gtin": "00359651029886",
                "sn": "7AYN7S3AXN4YG6K",
                "exp": "280430",
                "lot": "CYAZES25035A"
            },
            {
                "orignal_scan": "0100359651029886217AYN7S3AXN4YG6K1728043010CYAZES25035A",
                "ndc": "359651029886",
                "gtin": "00359651029886",
                "sn": "7AYN7S3AXN4YG6K",
                "exp": "280430",
                "lot": "CYAZES25035A"
            }
        ]
    },
    {
        "cabinet_number": 2,
        "fill_status": true,
        "ndc": "360505082919",
        "quantity": 1,
        "current_stored_medecine": {
            "PRODUCTID": "60505-0829_de4b94c3-9864-33f5-8afe-ec494562de52",
            "PRODUCTNDC": "60505-0829",
            "PRODUCTTYPENAME": "HUMAN PRESCRIPTION DRUG",
            "PROPRIETARYNAME": "Fluticasone Propionate",
            "PROPRIETARYNAMESUFFIX": "",
            "NONPROPRIETARYNAME": "Fluticasone Propionate",
            "DOSAGEFORMNAME": "SPRAY, METERED",
            "ROUTENAME": "NASAL",
            "STARTMARKETINGDATE": "20070919",
            "ENDMARKETINGDATE": "",
            "MARKETINGCATEGORYNAME": "ANDA",
            "APPLICATIONNUMBER": "ANDA077538",
            "LABELERNAME": "Apotex Corp.",
            "SUBSTANCENAME": "FLUTICASONE PROPIONATE",
            "ACTIVE_NUMERATOR_STRENGTH": "50",
            "ACTIVE_INGRED_UNIT": "ug/1",
            "PHARM_CLASSES": "Corticosteroid Hormone Receptor Agonists [MoA], Corticosteroid [EPC]",
            "DEASCHEDULE": "",
            "NDC_EXCLUDE_FLAG": "N",
            "LISTING_RECORD_CERTIFIED_THROUGH": "20261231",
            "gtin": "",
            "sn": "",
            "exp": "",
            "lot": "",
            "BARCODENDC": "360505082919"
        },
        "stored_medications": [
            {
                "orignal_scan": "360505082919",
                "ndc": "360505082919",
                "gtin": "",
                "sn": "",
                "exp": "",
                "lot": ""
            }
        ]
    },
    {
        "cabinet_number": 3,
        "fill_status": false,
        "ndc": "",
        "quantity": 0,
        "current_stored_medecine": {},
        "stored_medications": []
    },
    {
        "cabinet_number": 4,
        "fill_status": false,
        "ndc": "",
        "quantity": 0,
        "current_stored_medecine": {},
        "stored_medications": []
    }
]
```

### `fda_product_db.json`

This is the json file containing the fda database with all the medication information. This is created with a process using `tools/convert_nda_db_to_json.py` and `tools/convert_nda_db_to_optimized_json.py`. See "Rebuilding the FDA database" above.


### `clear_frame.py`

This file clears all the window so that we can switch from the dispensing screen to the loading screen, and only keep one window open at at a time

### `client_api.py`

This is a wrapper for `lock_lights_serial_input.py`. The calls to this function could be replaced with the equivalent calls in `lock_lights_serial_input.py`. This file is just an artifact of when we used a server-client with a raspberry pi over the internet

### `dispensing_screen.py`

This is file containing the contents of the dispensing screen.

![Dispensing screen](./readme-imgs/dispensing_screen.png)

Whenever you are focuesed on this screen, it is focused on NDC Scan search.
When an NDC is scanned, it searches if the medication is located in `medecine_data.json`. 
If it is located in our json file, then we begin the process of dispensing. First, it asks for the number of medications being dispensed.

![Dispensing count](./readme-imgs/dispensing_count.png)

After selected the number, each medication is scanned, and it must match the `"original_scan"` field of at least one the list of
stored medications in `medecine_data.json`.

![Dispensing verification](./readme-imgs/ndc_verification.png)

If it matched, then a popup will come up showing the verification being successful.
Else, a popup will come up showing an error.

The quantity and earliest expiration date is shown as labels underneath each compartment.

The edit button does the same thing as the load medication button.
The only difference is that it preselects the compartment to switch to.

The unload button is for deleting medications.
It will ask user if it wants to open the compartment to retrieve the medication.
Then, it will delete the contents of the cabinet in `medecine_data.json`, and update
the labels on the screen.

If any of the medications expire within 31 days, a popup will appear on first startup of the program, or when switching from the loading screen to the dispensing screen.

The Load medication button will clear this screen and then construction the loading screen. See documentation on `loading_screen.py` and `screen_controller.py`.

The Manual unlock button is currently broken, and doesn't work.

### `expiration_date_handler`

The function in this file searches `medecine_data.json` and finds the earliest expiration date of medications located in the file.


### `global_db.py`

We load the fda database into memory so that we don't need to wait 2 seconds whenever we need to query the database.

### `image_new.py`

This file handles downloading images of medications.
It searched the ndc code on `dailymed.nlm.nih.gov`, and finds the first image associated with that NDC. This is done with bs4 for searching through browser websites.

### `loading_screen.py`

![Loading screen](./readme-imgs/loading_screen.png)

This is where the loading screen is handled. Whenever this screen is focused on, the "Scan NDC Code" textbox is selected. Scan an NDC code or a 2d datamatrix of the medication, and it will search the FDA database for the medication.

It will find an image of the medication and download it. The next time the dispensing screen is opened, the image of the medication will appear there.

If the medication is already loaded in another drawer, this popup will appear asking the user if they want to switch to that drawer.

![Already loaded](./readme-imgs/already_loaded.png)

It will then enter a loop for scanning each medication that you would like to load.

![Loading Scan](./readme-imgs/loading_scan.png)

If any medication that doesn't have the same NDC code is loaded, it will cause an error.

![Wrong scan](./readme-imgs/wrong_load.png)

### `lock_lights_serial_input.py` and `arduino/LockLights/LockLights.ino`

This is the API for connecting to the arduino and sending commands.

Sending a byte of 1 through 4 will turn on the lights and unlock the corresponding drawer.

Sending a byte of 7 will turn everything off

The arduino measures the pressure sensor to detect if someone is pushing down on the drawer, and will unlock the drawer again if it is being pushed down upon.

### `lot_number_parser.py`

This is for handling 2d datamatrices. It will split the datamatrix into Global Trade Item Number (GTIN), Serial number (SN), Expiration date (EXP), and Lot number (LOT).

### `main.py`

This is the entrance to the program. It first calls the dispensing screen

### `screen_controller`

This is for switching between the loading screen and the dispensing screen

### `arduino/cup_and_belt_guide_demo/cup_and_belt_guide_demo.ino`

Demo firmware for the cup and belt guide, driven by two stepper motors with limit switches.
Send `0`/`1` over serial to home/open the cup, `2`/`3` to home/open the belt guide, and `4` to run a full load sequence.
This sketch is not connected to the Python app.

