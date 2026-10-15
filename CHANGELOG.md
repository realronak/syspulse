# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-15

### Added
- **Native GTK 4 Desktop UI**: Built purely with Python 3, GTK 4, PyGObject, Cairo, and psutil for Wayland and Linux desktops.
- **System Overview Dashboard**:
  - Live aggregate and per-core CPU meters with frequency telemetry.
  - Memory (RAM) and Swap usage gauges with used/available allocations.
  - Real-time download/upload network throughput rates and session totals.
  - Active filesystem mounts with storage capacity and utilization percentages.
  - Header telemetry displaying hostname, system uptime, and 1m/5m/15m load averages.
- **Cairo Vector Graphs**:
  - High-performance, anti-aliased real-time charts with smooth gradient fills and dashed reference grids.
  - Dedicated graphs for CPU utilization, RAM & Swap dual-series, and auto-scaling Network traffic.
  - Configurable historical depth buffer (30 to 300 data points).
- **Process Manager**:
  - Interactive searchable process list filterable by PID, process name, or user.
  - Sortable columns: PID, Name, User, CPU %, Memory %, Memory RSS, and Status.
  - Safe process termination with modal confirmation dialogs for graceful termination (`SIGTERM`) and force kill (`SIGKILL`).
- **Hardware & Thermal Telemetry**:
  - CPU package thermal readouts with status indications.
  - Detected hardware thermal zones (`k10temp`, `coretemp`, `amdgpu`, `nvme`, Wi-Fi PHY) with high and critical thresholds.
  - Cooling fan speed telemetry with fallback when hardware sensors are unexposed.
  - Direct Linux `/sys/class/thermal` fallback when kernel driver sensors are absent.
- **System Information & Storage**:
  - Detailed hardware and OS specifications: distribution, kernel release, architecture, CPU model, total memory/swap capacities, and boot uptime.
  - Complete filesystem partition table with mount points, device nodes, and filesystem formats.
- **Preferences & Customization**:
  - Sampling interval settings: 500 ms, 1.0 s, 2.0 s, 3.0 s, and 5.0 s (power saver).
  - Configurable graph history buffer length.
  - Temperature unit toggle (Celsius / Fahrenheit).
  - Preferred network interface selector (automatic aggregation or specific NIC).
  - Persistent JSON configuration stored in `~/.config/syspulse/config.json`.
- **Packaging & Desktop Integration**:
  - Standard PEP 621 packaging via `pyproject.toml` with console script entry point `syspulse`.
  - Command-line flags `--version` (`-v`) and `--help`.
  - Validated XDG desktop application entry (`syspulse.desktop`) and scalable SVG icon (`syspulse.svg`).
  - Automated unit test suite with 21 unit tests covering configuration, bounded history, collector reliability, process termination, Cairo drawing, and UI initialization.

### Changed
- Migrated hardcoded user paths in desktop launcher to generic XDG specification standards.
- Hardened thermal zone discovery against unreadable or permission-restricted `/sys/class/thermal` nodes.
- Protected process enumeration against race conditions from disappearing or zombie processes.
