"""Pharmacy drawer application. Hardware is opt-in and requires commissioning."""
from pathlib import Path
import sys

# Keep the supplied pure-Python dependencies available without a virtual environment.
# Licenses and package metadata are retained in the bundle alongside package sources.
_dependencies = Path(__file__).resolve().parents[1] / "runtime-dependencies.zip"
if _dependencies.is_file() and str(_dependencies) not in sys.path:
    sys.path.insert(0, str(_dependencies))
    sys.dont_write_bytecode = True
