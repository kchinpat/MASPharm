"""Compatibility entry point for the combined browser interface."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pharm.web import main

if __name__ == "__main__":
    main()
