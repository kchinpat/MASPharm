"""MAS/1 byte protocol. Acknowledgements are not physical sensor readings."""
from enum import IntEnum
import os
import threading


class ConnectionNotReady(OSError):
    """Connection/HELLO failed before an actuator command was attempted."""


class ResponseTimeout(OSError):
    """The serial read completed without a response."""


class Data(IntEnum):
    HELLO = 0
    UNLOCK_CABINET_1 = 1
    UNLOCK_CABINET_2 = 2
    UNLOCK_CABINET_3 = 3
    UNLOCK_CABINET_4 = 4
    LOCK_CABINET_1 = 5
    LOCK_CABINET_2 = 6
    LOCK_CABINET_3 = 7
    LOCK_CABINET_4 = 8
    LOCK_DRAWER = 10
    RGB_1_ON = 11
    RGB_2_ON = 12
    RGB_3_ON = 13
    RGB_4_ON = 14
    RGB_1_OFF = 15
    RGB_2_OFF = 16
    RGB_3_OFF = 17
    RGB_4_OFF = 18
    LOCK_ALL = 19
    SELECT_1 = 20
    SELECT_2 = 21
    SELECT_3 = 22
    SELECT_4 = 23

def box(value):
    if type(value) is not int or value not in range(1, 5):
        raise ValueError("Compartment must be an integer from 1 through 4.")
    return value

def setup_uart():
    from serial import Serial
    return Serial(port=os.environ.get("MAS_SERIAL_PORT", "/dev/serial0"), baudrate=9600,
                  timeout=2, write_timeout=2, exclusive=True)

class Controller:
    def __init__(self, factory=setup_uart):
        self.factory = factory
        self.uart = None
        self.lock = threading.Lock()

    def _exchange(self, command):
        if self.uart is None or not self.uart.is_open:
            raise OSError("Serial connection is unavailable.")
        self.uart.reset_input_buffer()
        if self.uart.write(bytes([int(command)])) != 1:
            raise OSError("Incomplete serial write.")
        response = self.uart.readline(128).decode("ascii", errors="replace").strip()
        expected = "MAS/1 READY" if command == Data.HELLO else f"MAS/1 ACK {int(command)}"
        if not response:
            raise ResponseTimeout(f"Firmware did not acknowledge command {int(command)}: timeout")
        if command == Data.HELLO and response == "MAS/1 DISABLED":
            raise OSError("MAS/1 firmware is installed, but actuator outputs are disabled "
                          "(HARDWARE_COMMISSIONED=0). Complete the wiring/lock setup before enabling outputs.")
        if response != expected:
            raise OSError(f"Firmware did not acknowledge command {int(command)}: {response!r}")

    def _handshake(self, attempts):
        # A USB Uno/Nano may still be booting. Only a silent HELLO is retried,
        # on the same connection. Never retry an actuator command or a rejection.
        for attempt in range(attempts):
            try:
                self._exchange(Data.HELLO)
                return
            except ResponseTimeout:
                if attempt == attempts - 1:
                    raise OSError("No MAS/1 readiness reply at 9600 baud. Check the selected COM port "
                                  "and upload this project's UI/LockLights.ino to the Arduino. "
                                  "A USB connection alone does not install the firmware.")

    def _close(self):
        if self.uart is not None:
            try:
                self.uart.close()
            finally:
                self.uart = None

    def command(self, command):
        if isinstance(command, bool):
            raise ValueError("Invalid command.")
        command = Data(command)
        with self.lock:
            try:
                try:
                    fresh = self.uart is None
                    if fresh:
                        self.uart = self.factory()
                    self._handshake(3 if fresh else 1)
                except (OSError, ValueError, ImportError) as exc:
                    raise ConnectionNotReady(str(exc)) from exc
                if command != Data.HELLO:
                    self._exchange(command)
            except Exception:
                self._close()
                raise

    def status(self):
        self.command(Data.HELLO)

    def open(self, number):
        self.command(Data(19 + box(number)))

    def lock_all(self):
        self.command(Data.LOCK_ALL)

    def close(self):
        with self.lock:
            self._close()

def open_drawer(drawer, controller):
    controller.open(drawer)

def rgbOn(number, controller):
    controller.command(Data(10 + box(number)))

def emUnlock(controller):
    raise ValueError("All-compartment emergency unlock is disabled pending the physical access specification.")
