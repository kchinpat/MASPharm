"""Exact, conservative package lookup. Identifiers are strings, never numbers."""
import json
import re
from pathlib import Path
from .barcodes import read_scan, aliases


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:-[0-9]+)*", value.strip()):
        raise ValueError("Enter a numeric package identifier; only digits and separating hyphens are supported.")
    return value.strip().replace("-", "")


class Catalog:
    def __init__(self, path):
        self.index = {}
        self.warning = ""
        path = Path(path)
        if not path.exists():
            self.warning = "No catalog installed. Enter package details manually; lookup is unavailable."
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                data = data.get("results")
            if not isinstance(data, list):
                raise ValueError("Catalog must be a product list or a results object.")
            for product in data:
                if not isinstance(product, dict):
                    continue
                packages = product.get("packaging") or []
                if not isinstance(packages, list):
                    continue
                valid = []
                for package in packages:
                    if not isinstance(package, dict):
                        continue
                    try:
                        code = identifier(package.get("package_ndc"))
                    except ValueError:
                        continue
                    item = {key: str(product.get(key) or "") for key in
                            ("generic_name", "brand_name", "labeler_name")}
                    item.update(ndc=package["package_ndc"], description=str(package.get("description") or ""))
                    self.index.setdefault(code, []).append(item)
                    valid.append(item)
                annotations = product.get("openfda") or {}
                upcs = annotations.get("upc", []) if isinstance(annotations, dict) else []
                if isinstance(upcs, list):
                    for upc in upcs:
                        try:
                            self.index.setdefault(identifier(upc), []).extend(valid)
                        except ValueError:
                            continue
            if not self.index:
                self.warning = "Catalog contains no usable packages. Manual entry is available."
        except (OSError, ValueError) as exc:
            self.warning = f"Catalog unavailable: {exc}"

    def lookup(self, scan):
        codes = aliases(read_scan(scan))
        matches = [item for code in codes for item in self.index.get(code, [])]
        unique = {json.dumps(item, sort_keys=True): item for item in matches}
        if len(unique) != 1:
            raise ValueError("No exact package match." if not unique else
                             "Ambiguous package match. Scan the package NDC or enter verified package details.")
        return dict(next(iter(unique.values())))

    def matches(self, scan, expected):
        if identifier(expected) in aliases(read_scan(scan)):
            return True
        try:
            return identifier(self.lookup(scan)["ndc"]) == identifier(expected)
        except ValueError:
            return False

    def loading_details(self, scan):
        """Use a valid scan for manual entry when no exact catalog match exists.

        Never carry a prior package's identity, lot or expiration into a new
        selection. An ambiguous lookup falls back to the actual scanned code,
        without choosing a catalog package on the operator's behalf.
        """
        parsed = read_scan(scan)
        code = parsed["code"]
        stock = {k: parsed[k] for k in ("lot", "expiry_date") if parsed[k]}
        try:
            return {**self.lookup(scan), **stock}, "Package found. Review lot, actual expiration and unit before loading."
        except ValueError as exc:
            return {"ndc": code, **stock}, (f"{exc} Scanned identifier retained. Enter the package details, "
                                  "lot, expiration and unit manually.")
