"""Exact, conservative package lookup. Identifiers are strings, never numbers."""
import json
import re
from pathlib import Path
from .barcodes import read_scan, aliases, drug_ndc


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:-[0-9]+)*", value.strip()):
        raise ValueError("Enter a numeric package identifier; only digits and separating hyphens are supported.")
    return value.strip().replace("-", "")


def unit_type(description):
    """The outer container in an FDA package description as a unit type, such as
    "bottle" for "100 TABLET in 1 BOTTLE, PLASTIC (0406-0512-01) / ...", or ""."""
    outer = re.split(r">| / |\*", description)[0]
    match = re.search(r"\bin [0-9.,]+ ([a-z][a-z -]*)", outer, re.I)
    unit = match[1].strip().lower() if match else ""
    return "" if unit == "not applicable" else unit


def shared(packages):
    """Medication fields every candidate package agrees on, or {} without a common name."""
    fields = {}
    for key in ("generic_name", "brand_name", "labeler_name"):
        values = {item[key] for item in packages}
        if len(values) == 1 and "" not in values:
            fields[key] = values.pop()
    units = {unit_type(item["description"]) for item in packages}
    if len(units) == 1 and "" not in units:
        fields["unit"] = units.pop()
    return fields if "generic_name" in fields else {}


def strength_text(product):
    """A catalog product's strength as printed on a label, such as "0.25 mg" for
    ".25 mg/1" or "5 mg / 325 mg" for two active ingredients, or ""."""
    ingredients = product.get("active_ingredients")
    amounts = [str(item["strength"]).strip() for item in ingredients if isinstance(item, dict) and item.get("strength")] \
        if isinstance(ingredients, list) else []
    return " / ".join(("0" + amount if amount.startswith(".") else amount).removesuffix("/1") for amount in amounts)


def read_json(path):
    """A catalog file's JSON. Plain, xz- and gzip-compressed JSON are told apart by
    their content, so a compressed catalog works whatever its file is named."""
    raw = Path(path).read_bytes()
    try:
        if raw.startswith(b"\xfd7zXZ\x00"):
            import lzma
            raw = lzma.decompress(raw)
        elif raw.startswith(b"\x1f\x8b"):
            import gzip
            raw = gzip.decompress(raw)
    except ImportError as exc:
        raise ValueError(f"This Python cannot read compressed catalogs ({exc.name} is missing).") from exc
    except Exception as exc:  # lzma.LZMAError, EOFError: a damaged or truncated download
        raise ValueError(f"The compressed catalog is damaged: {exc}") from exc
    return json.loads(raw.decode("utf-8-sig"))


class Catalog:
    def __init__(self, path):
        self.index = {}
        self.products = {}  # "labeler-product" NDC segments -> packages
        self.strengths = {}  # package identifier -> strength, kept apart so lookups match as before
        self.warning = ""
        path = Path(path)
        if not path.exists():
            self.warning = "No catalog installed. Enter package details manually; lookup is unavailable."
            return
        try:
            data = read_json(path)
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
                strength = strength_text(product)
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
                    if self.strengths.setdefault(code, strength) != strength:
                        self.strengths[code] = ""  # entries disagree, so show none rather than guess
                    valid.append(item)
                    segments = item["ndc"].strip().split("-")
                    if len(segments) == 3:
                        self.products.setdefault("-".join(segments[:2]), []).append(item)
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

    def strength(self, ndc):
        """A package's strength for display. It is never saved with stock."""
        try:
            return self.strengths.get(identifier(ndc), "")
        except ValueError:
            return ""

    def lookup(self, scan):
        parsed = read_scan(scan)
        # The NDC inside a drug barcode names one package, even where a product
        # lists one UPC for all its packages or a relabeler repeats that UPC.
        ndc = drug_ndc(parsed["code"])
        for codes in ([ndc] if ndc else [], aliases(parsed)):
            matches = [item for code in codes for item in self.index.get(code, [])]
            unique = {json.dumps(item, sort_keys=True): item for item in matches}
            if len(unique) == 1:
                return dict(next(iter(unique.values())))
        raise ValueError("No exact package match." if not unique else
                         "Ambiguous package match. Scan the package NDC or enter verified package details.")

    def similar(self, scan):
        """Packages sharing the scanned code or, failing that, the labeler and
        product segments of its NDC (4-4-2, 5-3-2 or 5-4-1)."""
        codes = aliases(read_scan(scan))
        found = [item for code in codes for item in self.index.get(code, [])]
        if not found:
            for code in codes:
                if len(code) == 10:
                    for size, end in ((4, 8), (5, 8), (5, 9)):
                        found += self.products.get(f"{code[:size]}-{code[size:end]}", [])
        return found

    def matches(self, scan, expected):
        if identifier(expected) in aliases(read_scan(scan)):
            return True
        try:
            return identifier(self.lookup(scan)["ndc"]) == identifier(expected)
        except ValueError:
            return False

    def loading_details(self, scan):
        """Fill the loading form from a scan, including the unit type read from
        the package description; keep the scan for manual entry otherwise.

        Never carry a prior package's identity, lot or expiration into a new
        selection. An ambiguous lookup falls back to the actual scanned code,
        without choosing a catalog package on the operator's behalf, but still
        fills the medication and unit when every related package agrees.
        """
        parsed = read_scan(scan)
        code = parsed["code"]
        stock = {k: parsed[k] for k in ("lot", "expiry_date") if parsed[k]}
        try:
            product = self.lookup(scan)
        except ValueError as exc:
            # Best effort: fill what every related catalog package agrees on,
            # but keep the scanned identifier rather than picking a package.
            guess = shared(self.similar(scan))
            if guess:
                filled = "Medication and unit type" if "unit" in guess else "Medication"
                return {**guess, "ndc": code, **stock}, (f"{exc} Scanned identifier retained. {filled} filled from "
                                                       "related catalog packages; check them against the label "
                                                       "and complete the remaining details.")
            return {"ndc": code, **stock}, (f"{exc} Scanned identifier retained. Enter the package details, "
                                  "lot, expiration and unit manually.")
        unit = unit_type(product["description"])
        return ({**product, **({"unit": unit} if unit else {}), **stock},
                "Package found. Review lot, actual expiration and unit before loading.")
