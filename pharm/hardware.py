"""Simulation, direct USB, and optional legacy HTTPS bench adapters."""
from dataclasses import dataclass
import json
import ssl
import urllib.error
import urllib.request
import time

from .serial_controller import ConnectionNotReady, Controller


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str
    # Unknown failures remain conservative. False requires positive knowledge
    # that connection setup failed before sending any actuator command.
    action_attempted: bool = True

    def __bool__(self):
        return self.ok


def compartment(value):
    if type(value) is not int or value not in range(1, 5):
        raise ValueError("Compartment must be an integer from 1 through 4.")
    return value


class Simulator:
    mode = "SIMULATION"

    def __init__(self):
        self.selected = None

    def open(self, number):
        self.selected = compartment(number)
        return Result(True, f"Simulated access to compartment {number}. No hardware moved.")

    def lock(self):
        self.selected = None
        return Result(True, "Simulated lock command completed.")

    def status(self):
        return Result(True, "Simulation ready. Physical lock state is not measured.")

    def close(self):
        pass


def usb_ports():
    """Enumerate descriptions without opening a port or probing firmware."""
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise ValueError("USB support requires pyserial. Install requirements-usb.txt with the launcher Python.") from exc
    return [(port.device, port.description) for port in list_ports.comports()]


def open_usb_port(port):
    from serial import Serial
    uart = Serial(port=port, baudrate=9600, timeout=2, write_timeout=2)
    try:
        # Opening an Uno or classic Nano USB port can reset it. Wait before
        # HELLO; the controller tolerates a further bounded startup delay.
        time.sleep(2)
        return uart
    except BaseException:
        uart.close()
        raise


class SerialHardware:
    def __init__(self, port, factory=None):
        if not isinstance(port, str) or not port.strip():
            raise ValueError("Select the Arduino's USB serial port.")
        self.port = port.strip()
        self.selected = None
        self.mode = f"USB BENCH | {self.port}"
        self.controller = Controller(factory if factory is not None else lambda: open_usb_port(self.port))

    def _run(self, action, message):
        try:
            action()
            return Result(True, message + " Physical lock state is not measured.")
        except ConnectionNotReady as exc:
            return Result(False, f"Arduino connection not ready on {self.port}: {exc}\n"
                          "No drawer command was sent. Close Arduino Serial Monitor or other apps using the port. "
                          "See docs/RUNNING.md for Uno firmware setup.", action_attempted=False)
        except (OSError, ValueError, ImportError) as exc:
            return Result(False, f"USB request failed: {exc}. Reconcile any attempted access before continuing.")

    def open(self, number):
        compartment(number)
        result = self._run(lambda: self.controller.open(number), f"Drawer {number}: firmware acknowledged access.")
        if result.ok:
            self.selected = number
        return result

    def lock(self):
        result = self._run(self.controller.lock_all, "Firmware acknowledged the lock request.")
        if result.ok:
            self.selected = None
        return result

    def status(self):
        return self._run(self.controller.status, "MAS/1 firmware ready.")

    def close(self):
        self.controller.close()


class HttpHardware:
    mode = "HARDWARE BENCH"

    def __init__(self, url, key, ca_file=None):
        if not url.startswith("https://") or not key:
            raise ValueError("Hardware mode requires an HTTPS API URL and an API key.")
        self.url = url.rstrip("/")
        self.key = key
        self.context = ssl.create_default_context(cafile=ca_file)

    def request(self, route, data=None):
        request = urllib.request.Request(
            self.url + route, data=json.dumps(data).encode() if data is not None else None,
            headers={"X-API-Key": self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5, context=self.context) as response:
                body = json.loads(response.read(65536))
                if not isinstance(body, dict) or body.get("protocol") != "MAS/1":
                    return Result(False, "Incompatible API response. Reconcile any attempted access.")
                return Result(body.get("ok") is True, str(body.get("message", "No device confirmation.")))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return Result(False, f"Device request failed: {exc}. Do not retry an uncertain operation.")

    def open(self, number):
        return self.request("/open_drawer", {"drawer": compartment(number)})

    def lock(self):
        return self.request("/lock_drawer", {})

    def status(self):
        return self.request("/status")

    def close(self):
        pass
