"""Compatibility imports for the shared laptop/Pi MAS/1 serial controller."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pharm.serial_controller import Controller, Data, box, setup_uart, open_drawer, rgbOn, emUnlock
