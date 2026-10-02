import threading
import unittest
from unittest.mock import Mock, patch

from pharm.hardware import HttpHardware, Simulator, Result, SerialHardware, open_usb_port, usb_ports
from rpi_folder_copy.lock_lights_serial_input import Controller, Data
from rpi_folder_copy.secure_api import create_app


class UART:
    def __init__(self, fail=False, ready=True, short=False):
        self.is_open = True
        self.sent = []
        self.fail, self.ready, self.short = fail, ready, short

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.sent.extend(data)
        return 0 if self.short else len(data)

    def readline(self, size):
        if self.sent[-1] == 0:
            return b"MAS/1 READY\n" if self.ready else b"MAS/1 DISABLED\n"
        return b"" if self.fail else f"MAS/1 ACK {self.sent[-1]}\n".encode()

    def close(self):
        self.is_open = False


class ProtocolTests(unittest.TestCase):
    def test_slow_usb_boot_retries_only_hello_on_same_port(self):
        uart = UART()
        uart.readline = Mock(side_effect=[b"", b"", b"MAS/1 READY\r\n", b"MAS/1 ACK 21\r\n"])
        factory = Mock(return_value=uart)
        self.assertTrue(SerialHardware("COM3", factory).open(2))
        self.assertEqual([0, 0, 0, 21], uart.sent)
        factory.assert_called_once_with()

    def test_silent_firmware_reports_setup_failure_without_access(self):
        uart = UART()
        uart.readline = Mock(return_value=b"")
        result = SerialHardware("COM3", lambda: uart).open(1)
        self.assertFalse(result.ok)
        self.assertFalse(result.action_attempted)
        self.assertIn("COM3", result.message)
        self.assertIn("UI/LockLights.ino", result.message)
        self.assertIn("No drawer command was sent", result.message)
        self.assertEqual([0, 0, 0], uart.sent)
        self.assertFalse(uart.is_open)

    def test_disabled_and_incompatible_firmware_are_not_retried(self):
        for reply, message in ((b"MAS/1 DISABLED\n", "HARDWARE_COMMISSIONED=0"),
                               (b"legacy response\n", "legacy response")):
            with self.subTest(reply=reply):
                uart = UART()
                uart.readline = Mock(return_value=reply)
                result = SerialHardware("COM3", lambda: uart).open(1)
                self.assertFalse(result.action_attempted)
                self.assertIn(message, result.message)
                self.assertEqual([0], uart.sent)

    def test_port_open_failure_has_no_access_attempt(self):
        factory = Mock(side_effect=OSError("Port busy"))
        result = SerialHardware("COM3", factory).open(1)
        self.assertFalse(result.ok)
        self.assertFalse(result.action_attempted)
        self.assertIn("Port busy", result.message)
        factory.assert_called_once_with()

    def test_lost_action_ack_remains_uncertain_and_is_not_retried(self):
        uart = UART(fail=True)
        result = SerialHardware("COM3", lambda: uart).open(1)
        self.assertFalse(result.ok)
        self.assertTrue(result.action_attempted)
        self.assertIn("Reconcile", result.message)
        self.assertEqual([0, 20], uart.sent)

    def test_connected_port_failure_does_not_run_boot_retries(self):
        uart = UART()
        hardware = SerialHardware("COM3", lambda: uart)
        self.assertTrue(hardware.status())
        uart.readline = Mock(return_value=b"")
        self.assertFalse(hardware.open(1).action_attempted)
        self.assertEqual([0, 0], uart.sent)

    def test_direct_usb_is_lazy_and_closes_port(self):
        uart = UART()
        calls = []
        def factory():
            calls.append(True)
            return uart
        hardware = SerialHardware("COM7", factory)
        self.assertEqual([], calls)
        self.assertTrue(hardware.open(2))
        self.assertEqual([0, 21], uart.sent)
        self.assertTrue(hardware.lock())
        self.assertEqual([0, 21, 0, 19], uart.sent)
        hardware.close()
        self.assertFalse(uart.is_open)

    def test_direct_usb_errors_return_failure_without_retry(self):
        for uart in (UART(ready=False), UART(fail=True)):
            hardware = SerialHardware("COM7", lambda: uart)
            self.assertFalse(hardware.open(1))
            self.assertLessEqual(len(uart.sent), 2)
            self.assertFalse(uart.is_open)

    def test_usb_reset_wait_and_windows_serial_options(self):
        with patch("serial.Serial") as serial, patch("pharm.hardware.time.sleep") as sleep:
            uart = open_usb_port("COM7")
            serial.assert_called_once_with(port="COM7", baudrate=9600, timeout=2, write_timeout=2)
            sleep.assert_called_once_with(2)
            self.assertIs(serial.return_value, uart)

    def test_enumeration_does_not_open_a_port(self):
        with patch("serial.tools.list_ports.comports", return_value=[]) as ports, patch("serial.Serial") as serial:
            self.assertEqual([], usb_ports())
            serial.assert_not_called()

    def test_pi_and_laptop_share_controller(self):
        from pharm.serial_controller import Controller as shared
        self.assertIs(Controller, shared)

    def test_selection_is_one_explicit_command_not_emergency_sequence(self):
        uart = UART()
        device = Controller(lambda: uart)
        device.open(1)
        self.assertEqual([0, 20], uart.sent)
        device.open(4)
        self.assertEqual([0, 20, 0, 23], uart.sent)

    def test_missing_ack_closes_connection_without_retry(self):
        uart = UART(fail=True)
        with self.assertRaises(OSError):
            Controller(lambda: uart).open(2)
        self.assertFalse(uart.is_open)
        self.assertEqual([0, 21], uart.sent)

    def test_disabled_firmware_blocks_mutations(self):
        uart = UART(ready=False)
        with self.assertRaises(OSError):
            Controller(lambda: uart).open(1)
        self.assertEqual([0], uart.sent)

    def test_invalid_input_never_writes(self):
        uart = UART()
        device = Controller(lambda: uart)
        for number in (0, 5, True, "1", -1):
            with self.subTest(number=number), self.assertRaises(ValueError):
                device.open(number)
        self.assertEqual([], uart.sent)

    def test_short_write_and_connection_failure_propagate(self):
        with self.assertRaises(OSError):
            Controller(lambda: UART(short=True)).status()
        with self.assertRaises(OSError):
            Controller(lambda: (_ for _ in ()).throw(OSError("No port"))).status()

    def test_commands_do_not_interleave(self):
        uart = UART()
        device = Controller(lambda: uart)
        threads = [threading.Thread(target=device.open, args=(n,)) for n in range(1, 5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual([0, 0, 0, 0], uart.sent[::2])
        self.assertEqual([20, 21, 22, 23], sorted(uart.sent[1::2]))

    def test_simulator_explicit_and_https_required(self):
        sim = Simulator()
        self.assertIn("No hardware", sim.open(2).message)
        self.assertEqual(2, sim.selected)
        self.assertTrue(sim.lock().ok)
        self.assertIsNone(sim.selected)
        with self.assertRaises(ValueError):
            HttpHardware("http://localhost:5000", "x" * 32)
        self.assertFalse(Result(False, "Failed"))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.uart = UART()
        self.app = create_app(Controller(lambda: self.uart), "x" * 32)
        self.app.logger.disabled = True
        self.client = self.app.test_client()
        self.headers = {"X-API-Key": "x" * 32}

    def test_routes_register_once_and_alternate_uses_same_factory(self):
        from rpi_folder_copy.secure_api_2 import create_app as alternate
        self.assertIs(create_app, alternate)
        self.assertEqual(8, len(list(self.app.url_map.iter_rules())))

    def test_unauthorized_never_opens_port(self):
        self.assertEqual(401, self.client.post("/open_drawer", json={"drawer": 1}).status_code)
        self.assertEqual([], self.uart.sent)

    def test_body_validation(self):
        for body in (None, [], "bad", {}, {"drawer": True}, {"drawer": "1"}, {"drawer": 5},
                     {"drawer": 1, "extra": 1}):
            with self.subTest(body=body):
                response = self.client.post("/open_drawer", json=body, headers=self.headers)
                self.assertEqual(400, response.status_code)
        self.assertEqual([], self.uart.sent)

    def test_oversized_request(self):
        response = self.client.post("/open_drawer", json={"drawer": "x" * 5000}, headers=self.headers)
        self.assertEqual(413, response.status_code)

    def test_open_lock_and_health_acknowledge_not_physical_state(self):
        for method, route, body in (("get", "/status", None), ("post", "/open_drawer", {"drawer": 1}),
                                    ("post", "/lock_drawer", {}), ("post", "/light", {"box": 2}),
                                    ("post", "/unlock_cabinet_lock", {"box": 3}),
                                    ("post", "/lock_cabinet_lock", {"box": 3})):
            response = getattr(self.client, method)(route, json=body, headers=self.headers)
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.json["ok"])
            self.assertEqual("unmeasured", response.json["physical_state"])

    def test_failure_is_not_success(self):
        self.uart.fail = True
        response = self.client.post("/open_drawer", json={"drawer": 1}, headers=self.headers)
        self.assertEqual(503, response.status_code)
        self.assertFalse(response.json["ok"])

    def test_emergency_not_silently_releases_all(self):
        response = self.client.post("/unlock", json={}, headers=self.headers)
        self.assertEqual(409, response.status_code)
        self.assertEqual([], self.uart.sent)


if __name__ == "__main__":
    unittest.main()
