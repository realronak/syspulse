# SysPulse ⚡

**SysPulse** is a lightweight, responsive, native Linux system monitor built specifically for Arch Linux / Omarchy running Hyprland over Wayland.

Built purely with **Python 3, GTK 4, PyGObject, Cairo, and psutil**, SysPulse adheres to strict desktop engineering principles: zero web technologies, zero Electron/Node.js bloat, bounded in-memory metrics buffers, non-blocking asynchronous sampling, and native Wayland performance.

---

## Key Features

1. **Overview Dashboard**:
   - Aggregate CPU utilization, live core frequencies, logical/physical core topology.
   - Per-core CPU utilization meters with dynamic threshold color coding.
   - RAM and Swap memory gauges with detailed used/available breakdowns.
   - Network I/O speeds (live download/upload rates and session cumulative transfers).
   - Filesystem storage usage and mount point monitors.
   - Header status telemetry: Hostname, system uptime, and 1m/5m/15m load averages.

2. **Real-time Historical Graphs**:
   - Anti-aliased Cairo vector area and line charts with smooth gradient fills and reference grids.
   - Dedicated full charts for CPU load, RAM & Swap dual-series, and auto-scaling Network traffic.
   - Fully customizable history duration (30 to 300 data points).

3. **Process Manager**:
   - Live searchable process list filterable by PID, process name, or user.
   - Sortable columns: PID, Name, User, CPU %, Memory %, RSS size, and status.
   - Safe process termination: Sends graceful `SIGTERM` (End Process) or `SIGKILL` (Force Kill) with modal confirmation dialogs.
   - Resilient against disappearing PIDs, permission boundaries, and zombie processes.

4. **Hardware & Thermal Sensors**:
   - Live CPU thermal package readouts with status indications.
   - Thermal zones for all detected hardware chips (`k10temp`, `amdgpu`, `nvme`, Wi-Fi PHY).
   - High and critical threshold tracking when supported by kernel drivers.
   - Cooling fan speed telemetry (with graceful, honest handling when sensors are not exposed).

5. **System Information & Storage**:
   - Comprehensive system specifications: OS distribution, kernel version, architecture, CPU model, total memory capacity, and boot time.
   - Partition table displaying mount points, device identifiers, filesystem types, and space utilization.

6. **Preferences & Customization**:
   - Configurable sampling cadence: 500 ms, 1.0 s, 2.0 s, 3.0 s, or 5.0 s (power saver).
   - Historical span buffer tuning.
   - Preferred network interface binding (automatic aggregation or specific NIC selection).
   - Temperature unit toggle (Celsius / Fahrenheit).
   - Persistent settings stored in `~/.config/syspulse/config.json`.

---

## Architecture & Directory Layout

```
syspulse/
├── assets/
│   ├── syspulse.desktop    # Validated XDG desktop application entry
│   └── syspulse.svg        # Clean vector application badge & icon
├── bin/
│   └── syspulse            # Standalone launcher script (auto-activates venv)
├── syspulse/
│   ├── __init__.py         # Version metadata & application ID
│   ├── __main__.py         # Module execution entry point
│   ├── app.py              # GTK 4 Application controller & lifecycle
│   ├── collector.py        # Thread-safe background collector & psutil/sysfs engine
│   ├── config.py           # Configuration manager & JSON serializer
│   ├── graphs.py           # Native Cairo vector drawing area widgets
│   ├── style.py            # Custom Wayland-native dark GTK 4 CSS theme
│   ├── ui.py               # Main window, navigation sidebar, and views
│   └── utils.py            # Formatting helpers (bytes, uptime, percentages)
├── tests/
│   ├── test_collector.py   # Metrics sampling, bounds, and error tests
│   ├── test_config.py      # Configuration validation & persistence tests
│   └── test_ui_and_graphs.py # UI initialization and graph rendering tests
├── README.md               # Project guide and documentation
└── .venv/                  # Project virtual environment (with --system-site-packages)
```

---

## Arch Linux / Omarchy Dependencies

SysPulse relies on Arch Linux native packages. You can install all runtime dependencies via `pacman`:

```bash
sudo pacman -S gtk4 python-gobject python-cairo python-psutil
```

*Note: SysPulse includes a self-contained virtual environment in `.venv/` containing `psutil`, which inherits system GTK 4 and Cairo without modifying your system packages.*

---

## Quick Start

### 1. Launch directly via the launcher script
```bash
/home/ron/syspulse/bin/syspulse
```
*(The launcher automatically detects the local environment and executes SysPulse.)*

### 2. Launch via Python module
```bash
cd /home/ron/syspulse
.venv/bin/python3 -m syspulse
```

---

## Running Automated Tests

All core algorithms, rate calculations, history buffer bounds, configuration validation, and UI components are fully covered by unit tests:

```bash
cd /home/ron/syspulse
.venv/bin/python3 -m unittest discover -s tests
```

---

## Desktop Entry Installation (Optional)

If you would like SysPulse to appear in your desktop application launcher (e.g., rofi, wofi, walker):

```bash
mkdir -p ~/.local/share/applications
ln -sf /home/ron/syspulse/assets/syspulse.desktop ~/.local/share/applications/syspulse.desktop
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

---

## Uninstallation Guide

Because SysPulse keeps all project files contained within its directory, removing it leaves zero residue on your system:

1. **Remove Desktop Launcher (if linked)**:
   ```bash
   rm -f ~/.local/share/applications/syspulse.desktop
   update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
   ```

2. **Remove User Configuration (optional)**:
   ```bash
   rm -rf ~/.config/syspulse
   ```

3. **Delete Project Directory**:
   ```bash
   rm -rf /home/ron/syspulse
   ```
