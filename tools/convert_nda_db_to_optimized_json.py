import json
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent.parent / "UI"

with open(UI_DIR / "fda_product_db.json", "r") as f:
    fda_product_db = json.load(f)

ndc_index = {item["PRODUCTNDC"]: item for item in fda_product_db if item.get("PRODUCTNDC")}

with open(UI_DIR / "fda_product_db_indexed.json", "w") as f:
    json.dump(ndc_index, f, indent=4)
