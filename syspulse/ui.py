"""
SysPulse GTK 4 Desktop User Interface
Modern, native dark GTK 4 UI with responsive sidebar navigation and live Cairo graphs.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from syspulse.collector import (
    MetricsCollector,
    ProcessItem,
    SystemSnapshot,
    terminate_process,
)
from syspulse.config import Config, save_config
from syspulse.graphs import CairoGraph
from syspulse.style import CSS_DATA, CSS_TEXT
from syspulse.utils import (
    format_bytes,
    format_percentage,
    format_temperature,
    format_uptime,
)


class ProcessRowObject(GObject.Object):
    """GObject container for Gtk.ColumnView process rows."""

    pid = GObject.Property(type=int)
    name = GObject.Property(type=str)
    user = GObject.Property(type=str)
    cpu = GObject.Property(type=float)
    mem = GObject.Property(type=float)
    rss_bytes = GObject.Property(type=GObject.TYPE_INT64)
    rss_str = GObject.Property(type=str)
    status = GObject.Property(type=str)

    def __init__(
        self,
        pid: int,
        name: str,
        user: str,
        cpu: float,
        mem: float,
        rss_bytes: int,
        rss_str: str,
        status: str,
    ) -> None:
        super().__init__()
        self.pid = pid
        self.name = name
        self.user = user
        self.cpu = cpu
        self.mem = mem
        self.rss_bytes = rss_bytes
        self.rss_str = rss_str
        self.status = status


class SysPulseWindow(Gtk.ApplicationWindow):
    """Main application window for SysPulse."""

    def __init__(self, app: Gtk.Application, config: Config, collector: MetricsCollector) -> None:
        super().__init__(application=app, title="SysPulse")
        self.config = config
        self.collector = collector

        self.set_default_size(1020, 680)
        self.set_title("SysPulse - System Monitor")

        # Apply CSS Theme
        self._setup_styling()

        # Main Layout: Sidebar + Content Area
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(main_box)

        # 1. Sidebar Navigation
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.sidebar_box.add_css_class("sidebar")
        self.sidebar_box.set_size_request(180, -1)
        main_box.append(self.sidebar_box)

        # App Brand Header
        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brand_box.set_margin_bottom(16)
        brand_box.set_margin_top(8)
        brand_box.set_margin_start(10)
        brand_lbl = Gtk.Label(label="⚡ SysPulse", xalign=0.0)
        brand_lbl.add_css_class("sidebar-title")
        brand_box.append(brand_lbl)
        self.sidebar_box.append(brand_box)

        # 2. Main Content Area
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)
        main_box.append(content_box)

        # Header Bar
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.header_box.add_css_class("header-bar")
        content_box.append(self.header_box)

        self.view_title_lbl = Gtk.Label(label="Dashboard", xalign=0.0)
        self.view_title_lbl.set_css_classes(["metric-card-title"])
        self.view_title_lbl.set_hexpand(True)
        self.header_box.append(self.view_title_lbl)

        # Top Pills: Hostname, Uptime, Load, Net
        self.host_pill = Gtk.Label(label="")
        self.host_pill.add_css_class("status-pill")
        self.header_box.append(self.host_pill)

        self.uptime_pill = Gtk.Label(label="")
        self.uptime_pill.add_css_class("status-pill")
        self.header_box.append(self.uptime_pill)

        self.load_pill = Gtk.Label(label="")
        self.load_pill.add_css_class("status-pill")
        self.header_box.append(self.load_pill)

        self.net_pill = Gtk.Label(label="")
        self.net_pill.add_css_class("status-pill")
        self.header_box.append(self.net_pill)

        # 3. Stack Pages
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        content_box.append(self.stack)

        # Initialize View Pages
        self.nav_buttons: Dict[str, Gtk.Button] = {}
        self._init_dashboard_page()
        self._init_graphs_page()
        self._init_processes_page()
        self._init_sensors_page()
        self._init_sysinfo_page()
        self._init_settings_page()

        # Select Dashboard by default
        self._switch_page("dashboard")

        # Process filter search cache
        self.current_search_query = ""

        # Schedule Periodic UI Refresh on GTK Main Thread
        self.timer_id = GLib.timeout_add(self.config.refresh_interval_ms, self._on_ui_tick)

    def _setup_styling(self) -> None:
        provider = Gtk.CssProvider()
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(CSS_TEXT)
        else:
            provider.load_from_data(CSS_DATA)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _add_nav_item(self, page_id: str, label: str, icon: str) -> None:
        btn = Gtk.Button(label=f"{icon}  {label}")
        btn.add_css_class("nav-button")
        btn.connect("clicked", lambda b, pid=page_id: self._switch_page(pid))
        self.sidebar_box.append(btn)
        self.nav_buttons[page_id] = btn

    def _switch_page(self, page_id: str) -> None:
        self.stack.set_visible_child_name(page_id)
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        titles = {
            "dashboard": "System Overview",
            "graphs": "Historical Graphs",
            "processes": "Process Manager",
            "sensors": "Hardware & Thermal Sensors",
            "sysinfo": "System Information & Storage",
            "settings": "SysPulse Settings",
        }
        self.view_title_lbl.set_text(titles.get(page_id, "SysPulse"))

    # --------------------------------------------------------------------------
    # 1. DASHBOARD PAGE
    # --------------------------------------------------------------------------
    def _init_dashboard_page(self) -> None:
        self._add_nav_item("dashboard", "Dashboard", "📊")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page_box.set_margin_top(16)
        page_box.set_margin_bottom(16)
        page_box.set_margin_start(18)
        page_box.set_margin_end(18)
        scroller.set_child(page_box)

        # Top 4 Metric Cards Grid
        top_grid = Gtk.Grid()
        top_grid.set_column_spacing(12)
        top_grid.set_row_spacing(12)
        top_grid.set_column_homogeneous(True)
        page_box.append(top_grid)

        # CPU Card
        self.cpu_card_box, self.cpu_val_lbl, self.cpu_sub_lbl, self.cpu_bar = self._create_metric_card(
            "CPU Utilization", "0.0%", "Freq: -- | Cores: --", "blue"
        )
        top_grid.attach(self.cpu_card_box, 0, 0, 1, 1)

        # Memory Card
        self.mem_card_box, self.mem_val_lbl, self.mem_sub_lbl, self.mem_bar = self._create_metric_card(
            "Memory (RAM)", "0.0%", "Used: -- / Total: --", "purple"
        )
        top_grid.attach(self.mem_card_box, 1, 0, 1, 1)

        # Swap Card
        self.swap_card_box, self.swap_val_lbl, self.swap_sub_lbl, self.swap_bar = self._create_metric_card(
            "Swap Memory", "0.0%", "Used: -- / Total: --", "orange"
        )
        top_grid.attach(self.swap_card_box, 2, 0, 1, 1)

        # Network Card
        self.net_card_box, self.net_val_lbl, self.net_sub_lbl, self.net_bar = self._create_metric_card(
            "Network Traffic", "↓ 0 B/s", "↑ 0 B/s | Total: --", "green"
        )
        top_grid.attach(self.net_card_box, 3, 0, 1, 1)

        # Mid Row: Per-Core CPU Gauges & Disks
        mid_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        mid_box.set_hexpand(True)
        page_box.append(mid_box)

        # Left: Per Core Utilization
        core_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        core_frame.add_css_class("metric-card")
        core_frame.set_hexpand(True)
        core_hdr = Gtk.Label(label="Per-Core CPU Utilization", xalign=0.0)
        core_hdr.add_css_class("metric-card-title")
        core_frame.append(core_hdr)

        self.core_bars_grid = Gtk.Grid()
        self.core_bars_grid.set_column_spacing(16)
        self.core_bars_grid.set_row_spacing(8)
        self.core_bars_grid.set_column_homogeneous(True)
        core_frame.append(self.core_bars_grid)
        self.core_widgets: List[Tuple[Gtk.Label, Gtk.ProgressBar, Gtk.Label]] = []
        mid_box.append(core_frame)

        # Right: Storage / Disks
        disk_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        disk_frame.add_css_class("metric-card")
        disk_frame.set_hexpand(True)
        disk_hdr = Gtk.Label(label="Filesystem Mounts", xalign=0.0)
        disk_hdr.add_css_class("metric-card-title")
        disk_frame.append(disk_hdr)

        self.disk_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        disk_frame.append(self.disk_list_box)
        mid_box.append(disk_frame)

        # Bottom Mini Graphs
        bottom_graphs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        bottom_graphs_box.set_hexpand(True)
        page_box.append(bottom_graphs_box)

        self.dash_cpu_graph = CairoGraph(
            title="CPU Load History (60s)",
            unit="%",
            fixed_max=100.0,
            primary_color=(0.22, 0.74, 0.97),
            primary_label="CPU",
        )
        self.dash_cpu_graph.set_content_height(140)
        bottom_graphs_box.append(self.dash_cpu_graph)

        self.dash_mem_graph = CairoGraph(
            title="Memory Usage History (60s)",
            unit="%",
            fixed_max=100.0,
            primary_color=(0.55, 0.36, 0.96),
            primary_label="RAM",
        )
        self.dash_mem_graph.set_content_height(140)
        bottom_graphs_box.append(self.dash_mem_graph)

        self.stack.add_named(scroller, "dashboard")

    def _create_metric_card(
        self, title: str, initial_val: str, initial_sub: str, bar_class: str
    ) -> Tuple[Gtk.Box, Gtk.Label, Gtk.Label, Gtk.ProgressBar]:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("metric-card")

        title_lbl = Gtk.Label(label=title, xalign=0.0)
        title_lbl.add_css_class("metric-card-title")
        card.append(title_lbl)

        val_lbl = Gtk.Label(label=initial_val, xalign=0.0)
        val_lbl.add_css_class("metric-card-val")
        card.append(val_lbl)

        bar = Gtk.ProgressBar()
        bar.set_fraction(0.0)
        bar.add_css_class(bar_class)
        card.append(bar)

        sub_lbl = Gtk.Label(label=initial_sub, xalign=0.0)
        sub_lbl.add_css_class("metric-card-sub")
        card.append(sub_lbl)

        return card, val_lbl, sub_lbl, bar

    # --------------------------------------------------------------------------
    # 2. GRAPHS PAGE
    # --------------------------------------------------------------------------
    def _init_graphs_page(self) -> None:
        self._add_nav_item("graphs", "Graphs", "📈")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)
        scroller.set_child(box)

        # 1. Detailed CPU Graph
        self.full_cpu_graph = CairoGraph(
            title="CPU Utilization History",
            unit="%",
            fixed_max=100.0,
            primary_color=(0.22, 0.74, 0.97),
            primary_label="Total CPU",
        )
        self.full_cpu_graph.set_content_height(160)
        box.append(self.full_cpu_graph)

        # 2. Detailed Memory Graph (RAM & Swap)
        self.full_mem_graph = CairoGraph(
            title="Memory & Swap Utilization",
            unit="%",
            fixed_max=100.0,
            primary_color=(0.55, 0.36, 0.96),
            secondary_color=(0.96, 0.62, 0.04),
            primary_label="RAM",
            secondary_label="Swap",
        )
        self.full_mem_graph.set_content_height(160)
        box.append(self.full_mem_graph)

        # 3. Detailed Network Graph (Rx & Tx rates)
        self.full_net_graph = CairoGraph(
            title="Network Traffic (Download & Upload)",
            unit="B/s",
            fixed_max=None,  # Auto-scaling
            primary_color=(0.22, 0.74, 0.97),
            secondary_color=(0.06, 0.73, 0.51),
            primary_label="Download",
            secondary_label="Upload",
            is_rate=True,
        )
        self.full_net_graph.set_content_height(160)
        box.append(self.full_net_graph)

        self.stack.add_named(scroller, "graphs")

    # --------------------------------------------------------------------------
    # 3. PROCESSES PAGE
    # --------------------------------------------------------------------------
    def _init_processes_page(self) -> None:
        self._add_nav_item("processes", "Processes", "⚙️")
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page_box.set_margin_top(14)
        page_box.set_margin_bottom(14)
        page_box.set_margin_start(18)
        page_box.set_margin_end(18)

        # Action & Filter Bar
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        page_box.append(action_bar)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search PID, process name, or user...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_process_search_changed)
        action_bar.append(self.search_entry)

        self.proc_count_lbl = Gtk.Label(label="0 processes")
        self.proc_count_lbl.add_css_class("status-pill")
        action_bar.append(self.proc_count_lbl)

        btn_term = Gtk.Button(label="End Process")
        btn_term.add_css_class("btn-action")
        btn_term.connect("clicked", lambda _: self._confirm_terminate_selected(force=False))
        action_bar.append(btn_term)

        btn_kill = Gtk.Button(label="Force Kill")
        btn_kill.add_css_class("btn-action")
        btn_kill.add_css_class("btn-danger")
        btn_kill.connect("clicked", lambda _: self._confirm_terminate_selected(force=True))
        action_bar.append(btn_kill)

        # Status / Feedback Banner
        self.proc_status_lbl = Gtk.Label(label="", xalign=0.0)
        self.proc_status_lbl.add_css_class("metric-card-sub")
        page_box.append(self.proc_status_lbl)

        # Data Model and ColumnView
        self.proc_store = Gio.ListStore(item_type=ProcessRowObject)

        # Custom Filter
        self.proc_filter = Gtk.CustomFilter.new(self._filter_process_item)
        self.proc_filter_model = Gtk.FilterListModel(model=self.proc_store, filter=self.proc_filter)

        # ColumnView
        self.proc_column_view = Gtk.ColumnView()
        self.proc_column_view.add_css_class("rich-list")

        # Built-in Interactive Sorting
        self.proc_sort_model = Gtk.SortListModel(
            model=self.proc_filter_model, sorter=self.proc_column_view.get_sorter()
        )
        self.proc_selection = Gtk.SingleSelection(model=self.proc_sort_model)
        self.proc_column_view.set_model(self.proc_selection)

        # Columns
        self._add_proc_column("PID", 65, lambda obj: str(obj.pid), sorter_fn=lambda a, b, *_: (a.pid > b.pid) - (a.pid < b.pid))
        self._add_proc_column("Process Name", 160, lambda obj: obj.name, sorter_fn=lambda a, b, *_: (a.name.lower() > b.name.lower()) - (a.name.lower() < b.name.lower()), expand=True)
        self._add_proc_column("User", 85, lambda obj: obj.user, sorter_fn=lambda a, b, *_: (a.user > b.user) - (a.user < b.user))
        self._add_proc_column("CPU %", 70, lambda obj: f"{obj.cpu:.1f}%", sorter_fn=lambda a, b, *_: (a.cpu > b.cpu) - (a.cpu < b.cpu))
        self._add_proc_column("Memory %", 75, lambda obj: f"{obj.mem:.1f}%", sorter_fn=lambda a, b, *_: (a.mem > b.mem) - (a.mem < b.mem))
        self._add_proc_column("Memory RSS", 95, lambda obj: obj.rss_str, sorter_fn=lambda a, b, *_: (a.rss_bytes > b.rss_bytes) - (a.rss_bytes < b.rss_bytes))
        self._add_proc_column("Status", 75, lambda obj: obj.status)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_child(self.proc_column_view)
        page_box.append(scroller)

        self.stack.add_named(page_box, "processes")

    def _add_proc_column(
        self,
        title: str,
        fixed_width: int,
        extractor: Callable[[ProcessRowObject], str],
        sorter_fn: Optional[Callable] = None,
        expand: bool = False,
    ) -> None:
        factory = Gtk.SignalListItemFactory()

        def _setup(factory, list_item):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            list_item.set_child(lbl)

        def _bind(factory, list_item):
            lbl = list_item.get_child()
            obj = list_item.get_item()
            if obj:
                lbl.set_text(extractor(obj))

        factory.connect("setup", _setup)
        factory.connect("bind", _bind)

        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        col.set_fixed_width(fixed_width)
        col.set_resizable(True)
        if expand:
            col.set_expand(True)
        if sorter_fn:
            col.set_sorter(Gtk.CustomSorter.new(sorter_fn))

        self.proc_column_view.append_column(col)

    def _filter_process_item(self, item: ProcessRowObject, *_) -> bool:
        if not self.current_search_query:
            return True
        q = self.current_search_query.lower()
        return (
            q in str(item.pid)
            or q in item.name.lower()
            or q in item.user.lower()
        )

    def _on_process_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.current_search_query = entry.get_text().strip()
        self.proc_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _confirm_terminate_selected(self, force: bool = False) -> None:
        item: Optional[ProcessRowObject] = self.proc_selection.get_selected_item()
        if not item:
            self.proc_status_lbl.set_text("Please select a process first.")
            return

        pid = item.pid
        name = item.name
        action_name = "Force Kill (SIGKILL)" if force else "End Process (SIGTERM)"

        dialog = Gtk.AlertDialog(
            message=f"{action_name} for '{name}'?",
            detail=f"Are you sure you want to send {'SIGKILL' if force else 'SIGTERM'} to process {pid}?\nThis action cannot be undone.",
            buttons=["Cancel", action_name],
        )

        def _on_dialog_response(source, result):
            try:
                btn_idx = source.choose_finish(result)
                if btn_idx == 1:
                    ok, msg = terminate_process(pid, force=force)
                    self.proc_status_lbl.set_text(msg)
                    # Trigger instant sample to update list
                    self._on_ui_tick()
            except Exception as e:
                self.proc_status_lbl.set_text(f"Action error: {e}")

        dialog.choose(self, None, _on_dialog_response)

    # --------------------------------------------------------------------------
    # 4. SENSORS PAGE
    # --------------------------------------------------------------------------
    def _init_sensors_page(self) -> None:
        self._add_nav_item("sensors", "Sensors", "🌡️")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)
        scroller.set_child(box)

        # Big CPU Temperature Banner Card
        self.sensor_banner_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.sensor_banner_card.add_css_class("metric-card")
        box.append(self.sensor_banner_card)

        sensor_card_hdr = Gtk.Label(label="CPU Thermal Package Reading", xalign=0.0)
        sensor_card_hdr.add_css_class("metric-card-title")
        self.sensor_banner_card.append(sensor_card_hdr)

        self.cpu_sensor_temp_lbl = Gtk.Label(label="-- °C", xalign=0.0)
        self.cpu_sensor_temp_lbl.add_css_class("metric-card-val")
        self.sensor_banner_card.append(self.cpu_sensor_temp_lbl)

        self.cpu_sensor_status_lbl = Gtk.Label(label="Thermal Status: Normal", xalign=0.0)
        self.cpu_sensor_status_lbl.add_css_class("metric-card-sub")
        self.sensor_banner_card.append(self.cpu_sensor_status_lbl)

        # Hardware Chips / Drives Temperatures List
        temps_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        temps_card.add_css_class("metric-card")
        box.append(temps_card)

        temps_hdr = Gtk.Label(label="Detected Hardware Thermal Zones", xalign=0.0)
        temps_hdr.add_css_class("metric-card-title")
        temps_card.append(temps_hdr)

        self.sensors_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        temps_card.append(self.sensors_container)

        # Fans Section
        fan_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fan_card.add_css_class("metric-card")
        box.append(fan_card)

        fan_hdr = Gtk.Label(label="Cooling Fan Readings", xalign=0.0)
        fan_hdr.add_css_class("metric-card-title")
        fan_card.append(fan_hdr)

        self.fans_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        fan_card.append(self.fans_container)

        self.stack.add_named(scroller, "sensors")

    # --------------------------------------------------------------------------
    # 5. SYSTEM INFO PAGE
    # --------------------------------------------------------------------------
    def _init_sysinfo_page(self) -> None:
        self._add_nav_item("sysinfo", "System Info", "ℹ️")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)
        scroller.set_child(box)

        # System Specifications Card
        spec_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        spec_card.add_css_class("metric-card")
        box.append(spec_card)

        spec_hdr = Gtk.Label(label="System & Hardware Specification", xalign=0.0)
        spec_hdr.add_css_class("metric-card-title")
        spec_card.append(spec_hdr)

        self.sysinfo_grid = Gtk.Grid()
        self.sysinfo_grid.set_column_spacing(24)
        self.sysinfo_grid.set_row_spacing(8)
        spec_card.append(self.sysinfo_grid)

        # Storage Filesystems Table Card
        mount_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mount_card.add_css_class("metric-card")
        box.append(mount_card)

        mount_hdr = Gtk.Label(label="Storage & Filesystem Partitions", xalign=0.0)
        mount_hdr.add_css_class("metric-card-title")
        mount_card.append(mount_hdr)

        self.sysinfo_disks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mount_card.append(self.sysinfo_disks_box)

        self.stack.add_named(scroller, "sysinfo")

    # --------------------------------------------------------------------------
    # 6. SETTINGS PAGE
    # --------------------------------------------------------------------------
    def _init_settings_page(self) -> None:
        self._add_nav_item("settings", "Settings", "🛠️")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)
        scroller.set_child(box)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        card.add_css_class("metric-card")
        box.append(card)

        hdr = Gtk.Label(label="Preferences & Monitoring Parameters", xalign=0.0)
        hdr.add_css_class("metric-card-title")
        card.append(hdr)

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(16)
        card.append(grid)

        # 1. Refresh Interval
        lbl_interval = Gtk.Label(label="Metrics Sampling Interval:", xalign=0.0)
        grid.attach(lbl_interval, 0, 0, 1, 1)

        self.intervals_map = [500, 1000, 2000, 3000, 5000]
        self.interval_dropdown = Gtk.DropDown.new_from_strings(
            ["500 ms (Fast)", "1.0 second (Default)", "2.0 seconds", "3.0 seconds", "5.0 seconds (Power saver)"]
        )
        cur_idx = 1
        if self.config.refresh_interval_ms in self.intervals_map:
            cur_idx = self.intervals_map.index(self.config.refresh_interval_ms)
        self.interval_dropdown.set_selected(cur_idx)
        grid.attach(self.interval_dropdown, 1, 0, 1, 1)

        # 2. Graph History
        lbl_hist = Gtk.Label(label="Graph Historical Span:", xalign=0.0)
        grid.attach(lbl_hist, 0, 1, 1, 1)

        self.history_map = [30, 60, 120, 300]
        self.history_dropdown = Gtk.DropDown.new_from_strings(
            ["30 data points", "60 data points (Default)", "120 data points", "300 data points"]
        )
        hist_idx = 1
        if self.config.history_points in self.history_map:
            hist_idx = self.history_map.index(self.config.history_points)
        self.history_dropdown.set_selected(hist_idx)
        grid.attach(self.history_dropdown, 1, 1, 1, 1)

        # 3. Temperature Unit
        lbl_temp = Gtk.Label(label="Temperature Unit:", xalign=0.0)
        grid.attach(lbl_temp, 0, 2, 1, 1)

        self.temp_dropdown = Gtk.DropDown.new_from_strings(["Celsius (°C)", "Fahrenheit (°F)"])
        self.temp_dropdown.set_selected(1 if self.config.temperature_unit == "F" else 0)
        grid.attach(self.temp_dropdown, 1, 2, 1, 1)

        # 4. Preferred Network Interface
        lbl_net = Gtk.Label(label="Preferred Network Interface:", xalign=0.0)
        grid.attach(lbl_net, 0, 3, 1, 1)

        snap = self.collector.get_snapshot()
        self.net_ifaces = ["auto"] + sorted(list(snap.network.interfaces.keys()))
        self.net_dropdown = Gtk.DropDown.new_from_strings(
            [("Automatic (All Active)" if iface == "auto" else iface) for iface in self.net_ifaces]
        )
        if self.config.preferred_interface in self.net_ifaces:
            self.net_dropdown.set_selected(self.net_ifaces.index(self.config.preferred_interface))
        grid.attach(self.net_dropdown, 1, 3, 1, 1)

        # Save Button & Status Label
        save_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        save_box.set_margin_top(10)
        card.append(save_box)

        btn_save = Gtk.Button(label="Save & Apply Changes")
        btn_save.add_css_class("btn-action")
        btn_save.add_css_class("btn-primary")
        btn_save.connect("clicked", self._on_save_settings_clicked)
        save_box.append(btn_save)

        self.settings_status_lbl = Gtk.Label(label="", xalign=0.0)
        self.settings_status_lbl.add_css_class("metric-card-sub")
        save_box.append(self.settings_status_lbl)

        self.stack.add_named(scroller, "settings")

    def _on_save_settings_clicked(self, _button: Gtk.Button) -> None:
        sel_interval_idx = self.interval_dropdown.get_selected()
        new_interval = self.intervals_map[sel_interval_idx]

        sel_hist_idx = self.history_dropdown.get_selected()
        new_hist = self.history_map[sel_hist_idx]

        new_unit = "F" if self.temp_dropdown.get_selected() == 1 else "C"

        sel_net_idx = self.net_dropdown.get_selected()
        new_iface = self.net_ifaces[sel_net_idx] if sel_net_idx < len(self.net_ifaces) else "auto"

        self.config.refresh_interval_ms = new_interval
        self.config.history_points = new_hist
        self.config.temperature_unit = new_unit
        self.config.preferred_interface = new_iface

        # Update running collector
        self.collector.set_interval_ms(new_interval)
        self.collector.set_history_points(new_hist)
        self.collector.set_preferred_interface(new_iface)

        # Reschedule timer
        if hasattr(self, "timer_id") and self.timer_id:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(new_interval, self._on_ui_tick)

        # Save to disk
        ok = save_config(self.config)
        if ok:
            self.settings_status_lbl.set_text("Settings saved and applied successfully!")
        else:
            self.settings_status_lbl.set_text("Failed to save settings to disk.")

    # --------------------------------------------------------------------------
    # PERIODIC UI REFRESH TICK
    # --------------------------------------------------------------------------
    def _on_ui_tick(self) -> bool:
        snap: SystemSnapshot = self.collector.get_snapshot()
        hist: Dict[str, List[float]] = self.collector.get_history()

        # Update Header Status Pills
        self.host_pill.set_text(f"🖥️ {snap.sys_info.hostname}")
        self.uptime_pill.set_text(f"⏱️ Uptime: {format_uptime(snap.sys_info.uptime_seconds)}")
        l1, l5, l15 = snap.sys_info.load_avg
        self.load_pill.set_text(f"⚡ Load: {l1:.2f}, {l5:.2f}, {l15:.2f}")
        self.net_pill.set_text(
            f"↓ {format_bytes(snap.network.rx_rate, rate=True)}  ↑ {format_bytes(snap.network.tx_rate, rate=True)}"
        )

        active_tab = self.stack.get_visible_child_name()

        # Always update Dashboard & Graphs data
        self._update_dashboard(snap, hist)
        self._update_graphs(snap, hist)

        # Lazy-update other pages when active
        if active_tab == "processes":
            self._update_processes(snap)
        elif active_tab == "sensors":
            self._update_sensors(snap)
        elif active_tab == "sysinfo":
            self._update_sysinfo(snap)

        return True

    def _update_dashboard(self, snap: SystemSnapshot, hist: Dict[str, List[float]]) -> None:
        # 1. CPU Card
        self.cpu_val_lbl.set_text(format_percentage(snap.cpu.total_percent))
        self.cpu_bar.set_fraction(max(0.0, min(1.0, snap.cpu.total_percent / 100.0)))
        freq_str = f"{snap.cpu.frequency_mhz:.0f} MHz" if snap.cpu.frequency_mhz > 0 else "N/A"
        self.cpu_sub_lbl.set_text(f"Freq: {freq_str} | {snap.cpu.logical_cores} Threads ({snap.cpu.physical_cores} Cores)")

        # 2. Memory Card
        self.mem_val_lbl.set_text(format_percentage(snap.memory.percent))
        self.mem_bar.set_fraction(max(0.0, min(1.0, snap.memory.percent / 100.0)))
        used_mem = format_bytes(snap.memory.used_bytes)
        tot_mem = format_bytes(snap.memory.total_bytes)
        self.mem_sub_lbl.set_text(f"Used: {used_mem} / {tot_mem} (Avail: {format_bytes(snap.memory.available_bytes)})")

        # 3. Swap Card
        self.swap_val_lbl.set_text(format_percentage(snap.memory.swap_percent))
        self.swap_bar.set_fraction(max(0.0, min(1.0, snap.memory.swap_percent / 100.0)))
        used_sw = format_bytes(snap.memory.swap_used_bytes)
        tot_sw = format_bytes(snap.memory.swap_total_bytes)
        self.swap_sub_lbl.set_text(f"Used: {used_sw} / {tot_sw}")

        # 4. Network Card
        self.net_val_lbl.set_text(f"↓ {format_bytes(snap.network.rx_rate, rate=True)}")
        self.net_sub_lbl.set_text(
            f"↑ {format_bytes(snap.network.tx_rate, rate=True)} | Tot: ↓ {format_bytes(snap.network.rx_total)} ↑ {format_bytes(snap.network.tx_total)}"
        )
        self.net_bar.set_fraction(min(1.0, (snap.network.rx_rate + snap.network.tx_rate) / 52428800.0))  # 50MB/s ceiling

        # Per-Core CPU Gauges
        cores = snap.cpu.per_core
        num_cores = len(cores)

        # Allocate widgets if not yet created or core count changed
        if len(self.core_widgets) != num_cores:
            # Clear old
            while self.core_bars_grid.get_first_child():
                self.core_bars_grid.remove(self.core_bars_grid.get_first_child())
            self.core_widgets.clear()

            # Columns in grid: 2 columns of core bars for compact view
            cols = 2 if num_cores > 4 else 1
            for i in range(num_cores):
                c_lbl = Gtk.Label(label=f"Core {i}", xalign=0.0)
                c_lbl.set_size_request(55, -1)
                c_bar = Gtk.ProgressBar()
                c_bar.set_hexpand(True)
                c_pct = Gtk.Label(label="0.0%", xalign=1.0)
                c_pct.set_size_request(45, -1)

                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row_box.append(c_lbl)
                row_box.append(c_bar)
                row_box.append(c_pct)

                col_idx = i % cols
                row_idx = i // cols
                self.core_bars_grid.attach(row_box, col_idx, row_idx, 1, 1)
                self.core_widgets.append((c_lbl, c_bar, c_pct))

        for i, val in enumerate(cores):
            if i < len(self.core_widgets):
                _, c_bar, c_pct = self.core_widgets[i]
                c_bar.set_fraction(max(0.0, min(1.0, val / 100.0)))
                c_pct.set_text(f"{val:.1f}%")

        # Disks List
        while self.disk_list_box.get_first_child():
            self.disk_list_box.remove(self.disk_list_box.get_first_child())

        for disk in snap.disks:
            d_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            top_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            m_lbl = Gtk.Label(label=f"<b>{disk.mountpoint}</b> ({disk.fstype})", use_markup=True, xalign=0.0)
            m_lbl.set_hexpand(True)
            u_lbl = Gtk.Label(
                label=f"{format_bytes(disk.used_bytes)} / {format_bytes(disk.total_bytes)} ({disk.percent:.1f}%)",
                xalign=1.0,
            )
            u_lbl.add_css_class("metric-card-sub")
            top_line.append(m_lbl)
            top_line.append(u_lbl)
            d_box.append(top_line)

            d_bar = Gtk.ProgressBar()
            d_bar.set_fraction(max(0.0, min(1.0, disk.percent / 100.0)))
            if disk.percent > 90:
                d_bar.add_css_class("red")
            elif disk.percent > 75:
                d_bar.add_css_class("orange")
            else:
                d_bar.add_css_class("green")
            d_box.append(d_bar)

            self.disk_list_box.append(d_box)

        # Mini Graphs
        self.dash_cpu_graph.update_data(hist.get("cpu", []))
        self.dash_mem_graph.update_data(hist.get("ram", []))

    def _update_graphs(self, _snap: SystemSnapshot, hist: Dict[str, List[float]]) -> None:
        self.full_cpu_graph.update_data(hist.get("cpu", []))
        self.full_mem_graph.update_data(hist.get("ram", []), hist.get("swap", []))
        self.full_net_graph.update_data(hist.get("net_rx", []), hist.get("net_tx", []))

    def _update_processes(self, snap: SystemSnapshot) -> None:
        procs: List[ProcessItem] = snap.processes
        self.proc_count_lbl.set_text(f"{len(procs)} processes")

        # Efficient in-place list store update
        items_to_add: List[ProcessRowObject] = []
        for p in procs:
            items_to_add.append(
                ProcessRowObject(
                    pid=p.pid,
                    name=p.name,
                    user=p.username,
                    cpu=p.cpu_percent,
                    mem=p.memory_percent,
                    rss_bytes=p.memory_rss,
                    rss_str=format_bytes(p.memory_rss),
                    status=p.status,
                )
            )

        # Re-populate store cleanly
        self.proc_store.remove_all()
        for item in items_to_add:
            self.proc_store.append(item)

    def _update_sensors(self, snap: SystemSnapshot) -> None:
        cpu_t = snap.sensors.cpu_temp
        unit = self.config.temperature_unit
        self.cpu_sensor_temp_lbl.set_text(format_temperature(cpu_t, unit=unit))

        if cpu_t is not None:
            if cpu_t < 60.0:
                self.cpu_sensor_status_lbl.set_text("Status: Optimal temperature")
            elif cpu_t < 80.0:
                self.cpu_sensor_status_lbl.set_text("Status: Moderate load / Warm")
            else:
                self.cpu_sensor_status_lbl.set_text("Status: High temperature warning")
        else:
            self.cpu_sensor_status_lbl.set_text("Status: No direct CPU thermal sensor reading available")

        # Populate Hardware Temperatures
        while self.sensors_container.get_first_child():
            self.sensors_container.remove(self.sensors_container.get_first_child())

        if snap.sensors.temperatures:
            for s in snap.sensors.temperatures:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                name_lbl = Gtk.Label(label=f"<b>{s.name}</b> - {s.label}", use_markup=True, xalign=0.0)
                name_lbl.set_hexpand(True)
                row.append(name_lbl)

                val_lbl = Gtk.Label(label=format_temperature(s.current_value, unit=unit), xalign=1.0)
                val_lbl.set_size_request(80, -1)
                row.append(val_lbl)

                crit_str = ""
                if s.critical_value:
                    crit_str = f"Crit: {format_temperature(s.critical_value, unit=unit)}"
                elif s.high_value:
                    crit_str = f"High: {format_temperature(s.high_value, unit=unit)}"

                crit_lbl = Gtk.Label(label=crit_str, xalign=1.0)
                crit_lbl.add_css_class("metric-card-sub")
                crit_lbl.set_size_request(100, -1)
                row.append(crit_lbl)

                self.sensors_container.append(row)
        else:
            empty_lbl = Gtk.Label(label="No hardware temperature sensors exposed via hwmon.", xalign=0.0)
            empty_lbl.add_css_class("metric-card-sub")
            self.sensors_container.append(empty_lbl)

        # Populate Fans
        while self.fans_container.get_first_child():
            self.fans_container.remove(self.fans_container.get_first_child())

        if snap.sensors.fans:
            for label, rpm in snap.sensors.fans:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                lbl = Gtk.Label(label=label, xalign=0.0)
                lbl.set_hexpand(True)
                row.append(lbl)
                rpm_lbl = Gtk.Label(label=f"{rpm} RPM", xalign=1.0)
                row.append(rpm_lbl)
                self.fans_container.append(row)
        else:
            no_fan_lbl = Gtk.Label(
                label="No hardware fan sensors detected on this system.", xalign=0.0
            )
            no_fan_lbl.add_css_class("metric-card-sub")
            self.fans_container.append(no_fan_lbl)

    def _update_sysinfo(self, snap: SystemSnapshot) -> None:
        # Populate Hardware Specs Grid
        while self.sysinfo_grid.get_first_child():
            self.sysinfo_grid.remove(self.sysinfo_grid.get_first_child())

        specs = [
            ("Operating System", snap.sys_info.os_name),
            ("Kernel Version", snap.sys_info.kernel),
            ("Architecture", snap.sys_info.cpu_arch),
            ("Hostname", snap.sys_info.hostname),
            ("CPU Model", snap.sys_info.cpu_model),
            ("CPU Cores / Threads", f"{snap.cpu.physical_cores} Physical / {snap.cpu.logical_cores} Logical"),
            ("Total Memory Capacity", format_bytes(snap.sys_info.total_memory_bytes)),
            ("Total Swap Capacity", format_bytes(snap.memory.swap_total_bytes)),
            ("System Uptime", format_uptime(snap.sys_info.uptime_seconds)),
        ]

        for i, (k, v) in enumerate(specs):
            lbl_k = Gtk.Label(label=k, xalign=0.0)
            lbl_k.add_css_class("metric-card-sub")
            lbl_v = Gtk.Label(label=f"<b>{v}</b>", use_markup=True, xalign=0.0)
            self.sysinfo_grid.attach(lbl_k, 0, i, 1, 1)
            self.sysinfo_grid.attach(lbl_v, 1, i, 1, 1)

        # Storage Partitions List
        while self.sysinfo_disks_box.get_first_child():
            self.sysinfo_disks_box.remove(self.sysinfo_disks_box.get_first_child())

        for disk in snap.disks:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            mp_lbl = Gtk.Label(label=f"<b>{disk.mountpoint}</b>", use_markup=True, xalign=0.0)
            mp_lbl.set_size_request(120, -1)
            row.append(mp_lbl)

            dev_lbl = Gtk.Label(label=f"{disk.device} ({disk.fstype})", xalign=0.0)
            dev_lbl.set_hexpand(True)
            row.append(dev_lbl)

            sz_lbl = Gtk.Label(
                label=f"{format_bytes(disk.used_bytes)} used / {format_bytes(disk.total_bytes)} ({disk.percent:.1f}%)",
                xalign=1.0,
            )
            row.append(sz_lbl)

            self.sysinfo_disks_box.append(row)
