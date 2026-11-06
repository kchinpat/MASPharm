"""Build the application's compact catalog, UI/db.json.xz, from an openFDA drug NDC export.

The official export (https://open.fda.gov/apis/drug/ndc/) is about 250 MB of JSON.
The application reads only a few fields of each product, so this keeps those
fields, in the export's own layout, and xz-compresses the result to a few MB.
Before writing anything it checks that the compact catalog gives exactly the
same lookups, unit types and strengths as the full export.

Run from the app folder, with the downloaded .json.zip or its extracted .json:

    python -B tools/build_catalog.py drug-ndc-0001-of-0001.json.zip

Then record the printed values in UI/db.source.json and restart the application.
"""
import argparse
import hashlib
import json
import lzma
import sys
import tempfile
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pharm.catalog import Catalog  # noqa: E402


def slim(product):
    """The parts of a product pharm/catalog.py reads, or None for one it skips."""
    packages = product.get("packaging") or []
    if not isinstance(packages, list):
        return None  # skipped entirely by the application, UPCs included
    kept = {key: product[key] for key in ("generic_name", "brand_name", "labeler_name") if product.get(key)}
    kept["packaging"] = [{key: package[key] for key in ("package_ndc", "description") if key in package}
                         for package in packages if isinstance(package, dict)]
    ingredients = product.get("active_ingredients")
    if isinstance(ingredients, list):
        strengths = [{"strength": item["strength"]} for item in ingredients if isinstance(item, dict) and item.get("strength")]
        if strengths:
            kept["active_ingredients"] = strengths
    annotations = product.get("openfda")
    if isinstance(annotations, dict) and isinstance(annotations.get("upc"), list) and annotations["upc"]:
        kept["openfda"] = {"upc": annotations["upc"]}
    return kept


def same(full, compact):
    return (full.index, full.products, full.strengths, full.warning) == \
           (compact.index, compact.products, compact.strengths, compact.warning)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help="openFDA drug NDC export (.json or .json.zip)")
    parser.add_argument("--output", type=Path, default=APP / "UI/db.json.xz")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as scratch:
        source = args.source
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as archive:
                (member,) = [name for name in archive.namelist() if name.endswith(".json")]
                source = Path(archive.extract(member, scratch))
        export = json.loads(source.read_text(encoding="utf-8-sig"))
        products = export.get("results") if isinstance(export, dict) else export
        if not isinstance(products, list):
            sys.exit("This is not an openFDA drug NDC export: no product list found.")
        compact = {"meta": export.get("meta", {}) if isinstance(export, dict) else {},
                   "results": [item for item in map(slim, filter(lambda p: isinstance(p, dict), products)) if item]}
        data = json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        print(f"Compressing {len(data) / 1e6:.1f} MB of catalog fields; this takes a minute or two...")
        packed = lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)

        candidate = Path(scratch) / "db.json.xz"
        candidate.write_bytes(packed)
        if not same(Catalog(source), Catalog(candidate)):
            sys.exit("The compact catalog does not match the export. Nothing was written.")
        args.output.write_bytes(packed)

    print(f"Wrote {args.output} after checking every lookup matches the full export.")
    print(json.dumps({"product_records": len(compact["results"]),
                      "installed_bytes": len(packed),
                      "installed_sha256": hashlib.sha256(packed).hexdigest(),
                      "installed_uncompressed_bytes": len(data)}, indent=2))


if __name__ == "__main__":
    main()
