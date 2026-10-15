import unittest

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from syspulse.collector import MetricsCollector
from syspulse.config import Config
from syspulse.graphs import CairoGraph
from syspulse.ui import ProcessRowObject, SysPulseWindow


class TestUIAndGraphs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Gtk.Application(application_id="io.github.syspulse.TestRunner")

    def test_cairo_graph_series(self):
        graph = CairoGraph(title="Test", unit="%", fixed_max=100.0)
        # Empty series
        graph.update_data([])
        self.assertEqual(graph.current_primary, 0.0)

        # Single point
        graph.update_data([50.0])
        self.assertEqual(graph.current_primary, 50.0)

        # Multiple points
        graph.update_data([10.0, 20.0, 30.0], [5.0, 15.0, 25.0])
        self.assertEqual(graph.current_primary, 30.0)
        self.assertEqual(graph.current_secondary, 25.0)

    def test_process_row_object(self):
        row = ProcessRowObject(
            pid=1234,
            name="systemd",
            user="root",
            cpu=1.5,
            mem=2.0,
            rss_bytes=10485760,
            rss_str="10.00 MiB",
            status="sleeping",
        )
        self.assertEqual(row.pid, 1234)
        self.assertEqual(row.name, "systemd")
        self.assertEqual(row.rss_bytes, 10485760)

    def test_syspulse_window_initialization(self):
        cfg = Config()
        collector = MetricsCollector(interval_ms=1000)
        win = SysPulseWindow(app=None, config=cfg, collector=collector)

        # Verify default child and page switching
        self.assertEqual(win.stack.get_visible_child_name(), "dashboard")

        pages = ["dashboard", "graphs", "processes", "sensors", "sysinfo", "settings"]
        for p in pages:
            win._switch_page(p)
            self.assertEqual(win.stack.get_visible_child_name(), p)
            # Verify UI tick runs without error on each page
            win._on_ui_tick()

        collector.stop()


if __name__ == "__main__":
    unittest.main()
