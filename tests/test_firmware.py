"""Execute the actual sketch with fake pins, serial and time, without a board.

Run from a Visual Studio developer shell on Windows, or with g++ on PATH.
The generated electrical profile is synthetic test data, never for upload.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = shutil.which("cl") or shutil.which("g++")


@unittest.skipUnless(COMPILER, "Firmware behavior tests require cl or g++ on PATH")
class FirmwareTests(unittest.TestCase):
    def build(self, enabled=False, level="LOW", lights=False, invalid=None):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            shutil.copy(ROOT / "UI/LockLights.ino", directory)
            profile = (ROOT / "UI/HardwareConfig.h").read_text()
            if enabled:
                profile = profile.replace("#define HARDWARE_COMMISSIONED 0", "#define HARDWARE_COMMISSIONED 1")
                profile = profile.replace("#define HARDWARE_PROFILE_VERIFIED 0", "#define HARDWARE_PROFILE_VERIFIED 1")
                profile = profile.replace("{-1, -1, -1, -1}", "{8, 10, 6, 7}")
                profile = profile.replace("RELEASE_LEVEL = -1", f"RELEASE_LEVEL = {level}")
                profile = profile.replace("RELEASE_PULSE_MS = 0", "RELEASE_PULSE_MS = 500")
                profile = profile.replace("RELEASE_REST_MS = 0", "RELEASE_REST_MS = 1000")
            if lights:
                profile = profile.replace("LIGHTS_ENABLED = false", "LIGHTS_ENABLED = true")
                profile = profile.replace("LED_DATA_PIN = -1", "LED_DATA_PIN = 4")
                profile = profile.replace("LED_COUNT = 0", "LED_COUNT = 91")
                profile = profile.replace("{0, 0, 0, 0, 0}", "{0, 23, 46, 69, 91}")
            if invalid:
                profile = profile.replace(*invalid)
            (directory / "HardwareConfig.h").write_text(profile)
            executable = directory / "behavior.exe"
            harness = ROOT / "tests/firmware"
            if Path(COMPILER).name.lower() == "cl.exe":
                args = [COMPILER, "/nologo", "/EHsc", "/std:c++14", f"/I{directory}",
                        f"/I{harness}", str(harness / "behavior.cpp"), f"/Fe:{executable}"]
            else:
                args = [COMPILER, "-std=c++11", f"-I{directory}", f"-I{harness}",
                        str(harness / "behavior.cpp"), "-o", str(executable)]
            result = subprocess.run(args, cwd=directory, capture_output=True, text=True, timeout=60)
            if invalid:
                self.assertNotEqual(0, result.returncode, "Invalid profile unexpectedly compiled")
                self.assertIn("Configure and verify", result.stdout + result.stderr)
            else:
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_disabled_firmware_never_drives_outputs(self):
        self.build()

    def test_pulse_rest_lock_and_timer_wrap_for_both_polarities(self):
        for level in ("LOW", "HIGH"):
            with self.subTest(level=level):
                self.build(enabled=True, level=level)

    def test_optional_lights_and_release_timing(self):
        self.build(enabled=True, lights=True)

    def test_invalid_enabled_profiles_fail_compilation(self):
        for invalid in (("{8, 10, 6, 7}", "{8, 8, 6, 7}"),
                        ("{8, 10, 6, 7}", "{0, 10, 6, 7}"),
                        ("RELEASE_PULSE_MS = 500", "RELEASE_PULSE_MS = 0"),
                        ("RELEASE_REST_MS = 1000", "RELEASE_REST_MS = 0"),
                        ("LED_DATA_PIN = 4", "LED_DATA_PIN = 8"),
                        ("#define HARDWARE_PROFILE_VERIFIED 1", "#define HARDWARE_PROFILE_VERIFIED 0")):
            with self.subTest(invalid=invalid):
                self.build(enabled=True, lights=True, invalid=invalid)


if __name__ == "__main__":
    unittest.main()
