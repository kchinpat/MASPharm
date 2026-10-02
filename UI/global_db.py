"""Compatibility catalog loader. Missing catalog is explicitly supported."""
import json
from pathlib import Path
path = Path(__file__).resolve().parent / "db.json"
prods = []
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        prods = data if isinstance(data, list) else data.get("results", [])
    except (OSError, ValueError, AttributeError):
        prods = []
