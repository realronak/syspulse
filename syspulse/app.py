"""
SysPulse Main Application Entry Point
"""

from __future__ import annotations

import sys
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib, Gtk

from syspulse.collector import MetricsCollector
from syspulse.config import load_config
from syspulse.ui import SysPulseWindow


class SysPulseApplication(Gtk.Application):
    """GTK 4 Application controller for SysPulse."""

    def __init__(self) -> None:
        super().__init__(
            application_id="io.github.syspulse.SysPulse",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.collector: Optional[MetricsCollector] = None
        self.window: Optional[SysPulseWindow] = None

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return

        cfg = load_config()
        self.collector = MetricsCollector(
            interval_ms=cfg.refresh_interval_ms,
            history_points=cfg.history_points,
            preferred_net_iface=cfg.preferred_interface,
        )
        self.collector.start()

        self.window = SysPulseWindow(app=self, config=cfg, collector=self.collector)
        self.window.connect("close-request", self._on_window_close)
        self.window.present()

    def _on_window_close(self, _window: Gtk.Window) -> bool:
        if self.collector:
            self.collector.stop()
        return False

    def do_shutdown(self) -> None:
        if self.collector:
            self.collector.stop()
        Gtk.Application.do_shutdown(self)


def main() -> int:
    app = SysPulseApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
