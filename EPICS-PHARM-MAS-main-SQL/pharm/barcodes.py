"""Package scans, including GS1 AIs 01, 17, 10 and 21.

FNC1 separators and parenthesized AIs are preferred. The team's existing
unseparated 01/21/17/10 labels are accepted only with one valid interpretation.
"""
import calendar
from datetime import date
import re


def expiry_date(value):
    if not re.fullmatch(r"[0-9]{6}", value):
        raise ValueError("GS1 expiration must contain six digits (YYMMDD).")
    year, month, day = 2000 + int(value[:2]), int(value[2:4]), int(value[4:])
    try:
        return date(year, month, day or calendar.monthrange(year, month)[1]).isoformat()
    except (ValueError, calendar.IllegalMonthError) as exc:
        raise ValueError("The package contains an invalid expiration date.") from exc


def _parse(value, require_gtin=True):
    fields = {}
    while value:
        value = value.lstrip("\x1d")
        if not value:
            break
        ai, value = value[:2], value[2:]
        if ai not in ("01", "17", "10", "21") or ai in fields:
            raise ValueError("Unsupported or repeated GS1 application identifier.")
        if ai in ("01", "17"):
            size = 14 if ai == "01" else 6
            part, value = value[:size], value[size:]
            if not re.fullmatch(r"[0-9]{%d}" % size, part):
                raise ValueError("The GS1 package scan is incomplete.")
            if ai == "17":
                expiry_date(part)
        elif "\x1d" in value:
            part, value = value.split("\x1d", 1)
        else:
            # Legacy scanners omit the variable-field separator before expiry.
            candidates = []
            if ai == "21" and "17" not in fields:
                for position in range(1, min(21, len(value))):
                    if value[position:position + 2] != "17":
                        continue
                    try:
                        tail = _parse(value[position:], require_gtin=False)
                        if "17" in tail and "01" not in tail and "21" not in tail:
                            candidates.append((value[:position], value[position:]))
                    except ValueError:
                        pass
            if len(candidates) > 1:
                raise ValueError("Ambiguous GS1 scan. Configure the scanner to send FNC1 separators.")
            part, value = candidates[0] if candidates else (value, "")
        if not part or len(part) > (20 if ai in ("10", "21") else 14) or any(ord(c) < 32 for c in part):
            raise ValueError("Invalid GS1 lot or serial number.")
        fields[ai] = part
    if require_gtin and "01" not in fields:
        raise ValueError("GS1 scan must include the package GTIN (01).")
    return fields


def read_scan(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ValueError("Scan a package barcode or enter its numeric identifier.")
    original = value.strip()
    value = original
    symbology = value.startswith(("]d2", "]C1", "]Q3"))
    if symbology:
        value = value[3:]
    parenthesized = value.startswith("(")
    if parenthesized:
        if not re.fullmatch(r"(?:\((?:01|17|10|21)\)[^()]+)+", value):
            raise ValueError("Invalid parenthesized GS1 scan.")
        value = re.sub(r"\((01|17|10|21)\)", lambda m: "\x1d" + m[1], value).lstrip("\x1d")
    gs1 = symbology or parenthesized or "\x1d" in value or (value.startswith("01") and len(value) >= 16)
    if not gs1:
        if not re.fullmatch(r"[0-9]+(?:-[0-9]+)*", value):
            raise ValueError("Unsupported package barcode format.")
        return {"original_scan": original, "code": value.replace("-", ""), "gtin": "", "serial": "", "lot": "", "expiry_date": ""}
    fields = _parse(value)
    gtin = fields["01"]
    return {"original_scan": original, "code": gtin, "gtin": gtin,
            "serial": fields.get("21", ""), "lot": fields.get("10", ""),
            "expiry_date": expiry_date(fields["17"]) if "17" in fields else ""}


def aliases(scan):
    codes = [scan["code"]]
    # GTIN-14 with indicator 0 and UPC-A padding 0 explicitly represents UPC-A.
    if scan["gtin"].startswith("00"):
        codes.append(scan["gtin"][2:])
    return codes
