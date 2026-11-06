# Installed medication catalog

Installed September 26, 2026: the official FDA National Drug Code Directory export published through openFDA, release **2026-09-26**.

- Source website: [FDA National Drug Code Directory](https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory).
- JSON distribution: [openFDA Drug NDC](https://open.fda.gov/apis/drug/ndc/).
- Current release manifest: [FDA download manifest](https://api.fda.gov/download.json).
- Installed application file: `UI/db.json.xz` (3.3 MB; compact form of the 246 MB export, see below).
- Source, retrieval time, checksums, counts and validation results: `UI/db.source.json`.
- Product records: **138,259**.
- Package records: **256,495**.

The source was identified from the previously inspected old archive's `PRODUCTID`, `PRODUCTNDC`, `NONPROPRIETARYNAME`, and `LISTING_RECORD_CERTIFIED_THROUGH` fields, plus its conversion scripts reading the tab-separated product table. These match the FDA NDC product-file schema. The exact original download URL was not recorded in those scripts. FDA documents the [product table](https://www.fda.gov/drugs/drug-approvals-and-databases/ndc-product-file-definitions) and [package table](https://www.fda.gov/drugs/drug-approvals-and-databases/ndc-package-file-definitions).

The current openFDA export includes package information and uses the JSON format already supported by this application. It is the complete official export, not a sample or a hand-built medication list. All partitions listed for this release were included (one partition). The API manifest, JSON release date and product count matched before installation. The previous September 25 local catalog backup and temporary catalog downloads were removed during the October 1, 2026 cleanup; the installed catalog and `UI/db.source.json` were preserved.

On November 6, 2026 the installed 246 MB export was replaced by a compact form. Its checksum was first confirmed against the one recorded at installation. `tools/build_catalog.py` kept every product and package record but only the fields the application reads (generic, brand and labeler names, package NDCs and descriptions, ingredient strengths and openFDA UPCs), in the export's own JSON layout with its `meta` block, and xz-compressed the result. Before writing, it confirmed that every identifier lookup, unit type and strength from the compact file is identical to the full export. The app reads plain, xz- and gzip-compressed JSON alike, and loads this catalog faster than the full export.

Validation checked 101 exact package lookups across the catalog, including preservation of leading zeros. Ambiguous identifiers continue to require an exact package match or manual entry. The application's catalog lookup does not treat listing certification dates as stock expiration dates. Stock counts, lots, package expiration and audit records were not changed.

Restart the application to load the updated default catalog. If a different catalog was previously selected through **Choose catalog**, select this project's `UI/db.json.xz` to use this release. Unlike the full export, the compact catalog is small enough to keep in Git, so `.gitignore` no longer excludes it; the source record is kept alongside it.

The data source and installed release can be checked in `UI/db.source.json`. For a future refresh, compare the official manifest's `results.drug.ndc.export_date`, obtain every partition, verify the export date and record counts, then run `python -B tools/build_catalog.py <downloaded .json.zip>` from the `app` folder. It replaces `UI/db.json.xz` only after validating the result, and prints the values to record in `UI/db.source.json`.
