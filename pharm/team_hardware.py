"""Explicit adapter for the team's pressure-sensor / byte-echo firmware.

It never opens a port at import, guesses a protocol, or retries an actuator.
Status reports output levels and open mode, not measured physical closure.
"""
import threading
from .hardware import Result, compartment, open_usb_port


class TeamSerialHardware:
    protocol = "TEAM-ECHO"

    def __init__(self, port, factory=None):
        if not isinstance(port, str) or not port.strip():
            raise ValueError("Select an Arduino COM port.")
        self.port = port.strip()
        self.mode = f"TEAM USB BENCH | {self.port}"
        self.factory = factory or (lambda: open_usb_port(self.port))
        self.uart = None
        self.mutex = threading.RLock()
        self.open_drawers = []
        self.output_unlocked = []

    def _write(self, command):
        self.uart.reset_input_buffer()
        if self.uart.write(bytes([command])) != 1:
            raise OSError("Incomplete serial write.")
        self.uart.flush()

    def _probe(self):
        if self.uart is None:
            self.uart = self.factory()
        if not self.uart.is_open:
            raise OSError("Serial port is closed.")
        self._write(0x30)
        # Team firmware returns exactly one status byte. MAS/1 returns text.
        response = self.uart.read(2)
        if len(response) != 1:
            raise OSError("No team status reply. Select the matching firmware profile.")
        mask = response[0]
        self.open_drawers = [n + 1 for n in range(4) if mask & (1 << n)]
        self.output_unlocked = [n + 1 for n in range(4) if mask & (1 << (n + 4))]

    def _echo(self, command):
        self._write(command)
        if self.uart.read(2) != bytes([command]):
            raise OSError("The cabinet did not acknowledge the command. Do not retry uncertain access.")

    def _run(self, action=None):
        with self.mutex:
            attempted = False
            try:
                self._probe()
                if action:
                    attempted = True
                    action()
                return Result(True, "Team firmware acknowledged the request. Confirm physical closure manually.")
            except (OSError, ValueError, ImportError) as exc:
                self.close()
                return Result(False, str(exc), action_attempted=attempted)

    def open(self, number):
        compartment(number)
        def select():
            self._echo(0x20)  # Secure other drawers before selecting one.
            self._echo(number)
            self.open_drawers = [number]
        return self._run(select)

    def lock(self):
        def secure():
            self._echo(7)
            self.open_drawers = []
            self.output_unlocked = []
        return self._run(secure)

    def status(self):
        return self._run()

    def close(self):
        with self.mutex:
            self.open_drawers = []
            self.output_unlocked = []
            if self.uart is not None:
                self.uart.close()
                self.uart = None
