import time
import unittest
from unittest.mock import MagicMock, patch

import psutil


from syspulse.collector import (
    MetricsCollector,
    MetricsHistory,
    SystemSnapshot,
    terminate_process,
)
from syspulse.utils import (
    format_bytes,
    format_percentage,
    format_temperature,
    format_uptime,
)


class TestUtils(unittest.TestCase):
    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(1024), "1.00 KiB")
        self.assertEqual(format_bytes(1048576), "1.00 MiB")
        self.assertEqual(format_bytes(1073741824), "1.00 GiB")
        self.assertEqual(format_bytes(5242880, rate=True), "5.00 MiB/s")

    def test_format_uptime(self):
        self.assertEqual(format_uptime(45), "00m 45s")
        self.assertEqual(format_uptime(3665), "01h 01m 05s")
        self.assertEqual(format_uptime(90000), "1d 01h 00m")

    def test_format_percentage(self):
        self.assertEqual(format_percentage(45.67), "45.7%")
        self.assertEqual(format_percentage(-5.0), "0.0%")
        self.assertEqual(format_percentage(150.0), "100.0%")

    def test_format_temperature(self):
        self.assertEqual(format_temperature(None), "N/A")
        self.assertEqual(format_temperature(50.0, unit="C"), "50.0 °C")
        self.assertEqual(format_temperature(50.0, unit="F"), "122.0 °F")


class TestMetricsHistory(unittest.TestCase):
    def test_bounded_history(self):
        hist = MetricsHistory(maxlen=5)
        for i in range(10):
            hist.append(time.time(), float(i), float(i * 2), 0.0, 100.0, 200.0)

        snaps = hist.get_snapshots()
        self.assertEqual(len(snaps["cpu"]), 5)
        self.assertEqual(snaps["cpu"], [5.0, 6.0, 7.0, 8.0, 9.0])
        self.assertEqual(snaps["ram"], [10.0, 12.0, 14.0, 16.0, 18.0])

    def test_resize_history(self):
        hist = MetricsHistory(maxlen=10)
        for i in range(10):
            hist.append(float(i), float(i), 0.0, 0.0, 0.0, 0.0)

        hist.set_maxlen(3)
        snaps = hist.get_snapshots()
        self.assertEqual(len(snaps["cpu"]), 3)
        self.assertEqual(snaps["cpu"], [7.0, 8.0, 9.0])


class TestMetricsCollector(unittest.TestCase):
    def setUp(self):
        self.collector = MetricsCollector(interval_ms=1000, history_points=10)

    def tearDown(self):
        self.collector.stop()

    def test_sample_snapshot(self):
        snap = self.collector.get_snapshot()
        self.assertIsInstance(snap, SystemSnapshot)
        self.assertGreaterEqual(snap.cpu.logical_cores, 1)
        self.assertGreater(snap.memory.total_bytes, 0)
        self.assertIsInstance(snap.disks, list)
        self.assertIsInstance(snap.processes, list)
        self.assertIsNotNone(snap.sys_info.kernel)

    def test_terminate_nonexistent_process(self):
        # PID 999999999 should not exist
        success, msg = terminate_process(999999999)
        self.assertFalse(success)
        self.assertIn("no longer exists", msg.lower())

    def test_terminate_process_mocked_success(self):
        with patch("psutil.Process") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "dummy"
            mock_proc_cls.return_value = mock_proc

            # Test SIGTERM
            ok, msg = terminate_process(12345, force=False)
            self.assertTrue(ok)
            mock_proc.terminate.assert_called_once()
            self.assertIn("SIGTERM", msg)

            # Test SIGKILL
            ok, msg = terminate_process(12345, force=True)
            self.assertTrue(ok)
            mock_proc.kill.assert_called_once()
            self.assertIn("SIGKILL", msg)

    def test_terminate_process_access_denied(self):
        with patch("psutil.Process", side_effect=psutil.AccessDenied()):
            ok, msg = terminate_process(1)
            self.assertFalse(ok)
            self.assertIn("Permission denied", msg)

    def test_missing_sensors_graceful_handling(self):
        with patch("psutil.sensors_temperatures", side_effect=Exception("Sensor error")):
            snap = self.collector._sample_sensors()
            # Must not crash, should return a valid SensorSnapshot
            self.assertIsNotNone(snap)
            self.assertIsInstance(snap.temperatures, list)

    def test_disappearing_process_handling(self):
        proc_good = MagicMock()
        proc_good.info = {
            "pid": 42,
            "name": "good_proc",
            "username": "user",
            "cpu_percent": 10.0,
            "memory_percent": 5.0,
            "memory_info": MagicMock(rss=1024),
            "status": "running",
        }

        proc_dying = MagicMock()
        type(proc_dying).info = unittest.mock.PropertyMock(side_effect=psutil.NoSuchProcess(pid=99))

        with patch("psutil.process_iter", return_value=[proc_good, proc_dying]):
            procs = self.collector._sample_processes()
            self.assertEqual(len(procs), 1)
            self.assertEqual(procs[0].pid, 42)

    def test_disk_usage_oserror_graceful_handling(self):
        fake_partition = MagicMock()
        fake_partition.device = "/dev/sda1"
        fake_partition.mountpoint = "/mnt/fake"
        fake_partition.fstype = "ext4"

        with patch("psutil.disk_partitions", return_value=[fake_partition]), \
             patch("psutil.disk_usage", side_effect=OSError("Disk stalled")):
            # _sample must not raise exception
            self.collector._sample()
            snap = self.collector.get_snapshot()
            self.assertIsInstance(snap, SystemSnapshot)

    def test_get_cpu_model_name(self):
        from unittest.mock import mock_open
        from syspulse.collector import get_cpu_model_name

        fake_cpuinfo = "processor : 0\nmodel name : AMD Ryzen 7 5700U\n"
        with patch("builtins.open", mock_open(read_data=fake_cpuinfo)):
            model = get_cpu_model_name()
            self.assertEqual(model, "AMD Ryzen 7 5700U")

    def test_cli_version_flag(self):
        import sys
        from io import StringIO
        from syspulse.app import main

        orig_argv = sys.argv
        orig_stdout = sys.stdout
        try:
            sys.argv = ["syspulse", "--version"]
            sys.stdout = StringIO()
            ret = main()
            self.assertEqual(ret, 0)
            self.assertIn("SysPulse 1.0.0", sys.stdout.getvalue())
        finally:
            sys.argv = orig_argv
            sys.stdout = orig_stdout


if __name__ == "__main__":
    unittest.main()


