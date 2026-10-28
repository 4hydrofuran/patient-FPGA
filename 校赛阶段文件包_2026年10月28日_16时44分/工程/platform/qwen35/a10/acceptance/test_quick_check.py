import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("quick", Path(__file__).with_name("quick_check.py"))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class IntakeTests(unittest.TestCase):
    def test_hwmon_only_board_layout(self):
        with tempfile.TemporaryDirectory() as d:
            thermal=Path(d)/'thermal';thermal.mkdir()
            hwmon=Path(d)/'hwmon';sensor=hwmon/'hwmon0';sensor.mkdir(parents=True)
            (sensor/'name').write_text('ams')
            for i,value in enumerate([34023,32516,31435],1):
                (sensor/f'temp{i}_input').write_text(str(value))
            values=q.temperatures(thermal,hwmon)
            self.assertEqual([t['celsius'] for t in values],[34.023,32.516,31.435])
            self.assertTrue(all(t['source']=='hwmon' for t in values))
            self.assertIsNone(q.cpu_gate('aarch64','MemAvailable: 3578232 kB',values,True))

    def test_bad_sensor_blocks_even_with_good_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            thermal=Path(d)/'thermal';thermal.mkdir()
            hwmon=Path(d)/'hwmon';sensor=hwmon/'hwmon0';sensor.mkdir(parents=True)
            (sensor/'temp1_input').write_text('35000')
            (sensor/'temp2_input').write_text('broken')
            values=q.temperatures(thermal,hwmon)
            self.assertEqual(len(values),2)
            self.assertIsNone(values[1]['celsius'])
            self.assertIsNotNone(q.cpu_gate('aarch64','MemAvailable: 500000 kB',values,True))

    def test_invalid_numeric_temperature_refuses(self):
        for value in [float('nan'),float('inf'),None,0,-5,151,'35',True]:
            self.assertIsNotNone(q.cpu_gate('aarch64','MemAvailable: 500000 kB',[{'celsius':35},{'celsius':value}],True))

    def test_both_temperature_paths_and_hot_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            thermal=Path(d)/'thermal';zone=thermal/'thermal_zone0';zone.mkdir(parents=True)
            hwmon=Path(d)/'hwmon';sensor=hwmon/'hwmon0';sensor.mkdir(parents=True)
            (zone/'temp').write_text('35000')
            (zone/'type').write_text('soc')
            (sensor/'temp1_input').write_text('60000')
            values=q.temperatures(thermal,hwmon)
            self.assertEqual([v['source'] for v in values],['thermal','hwmon'])
            self.assertIn('60 C',q.temperature_gate(values))

    def test_unreadable_sensor_and_after_gate(self):
        with tempfile.TemporaryDirectory() as d:
            thermal=Path(d)/'thermal';zone=thermal/'thermal_zone0';zone.mkdir(parents=True)
            values=q.temperatures(thermal,Path(d)/'hwmon')
            self.assertEqual(len(values),1)
            self.assertIsNone(values[0]['celsius'])
            self.assertIsNotNone(q.temperature_gate(values))
            self.assertIsNotNone(q.temperature_gate([]))

    def test_sensor_cap_and_oversize_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            thermal=Path(d)/'thermal'
            hwmon=Path(d)/'hwmon';sensor=hwmon/'hwmon0';sensor.mkdir(parents=True)
            for i in range(17):
                (sensor/f'temp{i}_input').write_text('35000')
            values=q.temperatures(thermal,hwmon)
            self.assertIsNotNone(q.temperature_gate(values))
            (sensor/'temp0_input').write_text('3'*129)
            values=q.temperatures(thermal,hwmon)
            self.assertTrue(any(v.get('reason','').startswith('Temperature reading exceeds') for v in values))

    def test_memory_unknown_refuses(self):
        self.assertIsNotNone(q.cpu_gate("aarch64", "", [{"celsius": 35}], True))

    def test_low_memory_refuses(self):
        self.assertIsNotNone(q.cpu_gate("aarch64", "MemAvailable: 10000 kB", [{"celsius": 35}], True))

    def test_temperature_unknown_refuses(self):
        self.assertIsNotNone(q.cpu_gate("aarch64", "MemAvailable: 500000 kB", [], True))

    def test_hot_refuses(self):
        self.assertIsNotNone(q.cpu_gate("aarch64", "MemAvailable: 500000 kB", [{"celsius": 60}], True))

    def test_identity_refuses(self):
        for machine, confirmed in [("x86_64", True), ("aarch64", False)]:
            self.assertIsNotNone(q.cpu_gate(machine, "MemAvailable: 500000 kB", [{"celsius": 35}], confirmed))

    def test_good_gate_unit_fixture_not_board(self):
        self.assertIsNone(q.cpu_gate("aarch64", "MemAvailable: 500000 kB", [{"celsius": 35}], True))

    def test_missing_file_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(q.read(Path(d) / "missing")["status"], "NOT_READ")

    def test_bounded_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "data"
            p.write_bytes(b"a" * (q.CAP + 2))
            self.assertTrue(q.read(p)["truncated"])

    def test_command_failure_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            result = q.command([sys.executable, "-c", "raise SystemExit(7)"], Path(d), "failed")
            self.assertEqual(result["exit_code"], 7)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue((Path(d) / "failed.stderr").exists())

    def test_cpu_only_timeout_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            result = q.command([sys.executable, "-c", "import time; time.sleep(5)"], Path(d), "timeout", .1)
            self.assertEqual(result["status"], "TIMEOUT")
            self.assertIsNone(result["exit_code"])

    def test_pc_board_entry_refused(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "report"
            r = subprocess.run([sys.executable, str(Path(q.__file__)), "--output", str(dest), "--board-label", "PC_FIXTURE", "--confirm-kv260"], capture_output=True)
            self.assertEqual(r.returncode, 2)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
