"""
SysPulse Metrics Collector Module
Thread-safe, resilient system metrics collector with bounded historical tracking.
"""

from __future__ import annotations

import collections
import os
import platform
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil


@dataclass
class CpuSnapshot:
    total_percent: float = 0.0
    per_core: List[float] = field(default_factory=list)
    logical_cores: int = 1
    physical_cores: int = 1
    frequency_mhz: float = 0.0


@dataclass
class MemorySnapshot:
    total_bytes: int = 0
    used_bytes: int = 0
    available_bytes: int = 0
    percent: float = 0.0
    swap_total_bytes: int = 0
    swap_used_bytes: int = 0
    swap_percent: float = 0.0


@dataclass
class DiskPartitionSnapshot:
    device: str
    mountpoint: str
    fstype: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


@dataclass
class NetworkInterfaceSnapshot:
    name: str
    rx_bytes_sec: float = 0.0
    tx_bytes_sec: float = 0.0
    rx_total_bytes: int = 0
    tx_total_bytes: int = 0
    is_up: bool = True


@dataclass
class NetworkSnapshot:
    interfaces: Dict[str, NetworkInterfaceSnapshot] = field(default_factory=dict)
    active_interface: str = "auto"
    rx_rate: float = 0.0  # Selected or aggregate B/s
    tx_rate: float = 0.0  # Selected or aggregate B/s
    rx_total: int = 0
    tx_total: int = 0


@dataclass
class ProcessItem:
    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    status: str


@dataclass
class SensorDevice:
    name: str
    label: str
    current_value: float
    high_value: Optional[float] = None
    critical_value: Optional[float] = None
    unit: str = "°C"


@dataclass
class SensorSnapshot:
    cpu_temp: Optional[float] = None
    temperatures: List[SensorDevice] = field(default_factory=list)
    fans: List[Tuple[str, int]] = field(default_factory=list)


@dataclass
class SystemInfo:
    hostname: str = ""
    os_name: str = ""
    kernel: str = ""
    cpu_model: str = ""
    cpu_arch: str = ""
    total_memory_bytes: int = 0
    uptime_seconds: float = 0.0
    load_avg: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class SystemSnapshot:
    timestamp: float = 0.0
    cpu: CpuSnapshot = field(default_factory=CpuSnapshot)
    memory: MemorySnapshot = field(default_factory=MemorySnapshot)
    disks: List[DiskPartitionSnapshot] = field(default_factory=list)
    network: NetworkSnapshot = field(default_factory=NetworkSnapshot)
    sensors: SensorSnapshot = field(default_factory=SensorSnapshot)
    sys_info: SystemInfo = field(default_factory=SystemInfo)
    processes: List[ProcessItem] = field(default_factory=list)


class MetricsHistory:
    """Bounded circular history buffers for real-time charting."""

    def __init__(self, maxlen: int = 60) -> None:
        self.maxlen = maxlen
        self.timestamps: collections.deque[float] = collections.deque(maxlen=maxlen)
        self.cpu_history: collections.deque[float] = collections.deque(maxlen=maxlen)
        self.ram_history: collections.deque[float] = collections.deque(maxlen=maxlen)
        self.swap_history: collections.deque[float] = collections.deque(maxlen=maxlen)
        self.net_rx_history: collections.deque[float] = collections.deque(maxlen=maxlen)
        self.net_tx_history: collections.deque[float] = collections.deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def set_maxlen(self, new_maxlen: int) -> None:
        with self.lock:
            self.maxlen = new_maxlen
            self.timestamps = collections.deque(self.timestamps, maxlen=new_maxlen)
            self.cpu_history = collections.deque(self.cpu_history, maxlen=new_maxlen)
            self.ram_history = collections.deque(self.ram_history, maxlen=new_maxlen)
            self.swap_history = collections.deque(self.swap_history, maxlen=new_maxlen)
            self.net_rx_history = collections.deque(self.net_rx_history, maxlen=new_maxlen)
            self.net_tx_history = collections.deque(self.net_tx_history, maxlen=new_maxlen)

    def append(self, timestamp: float, cpu: float, ram: float, swap: float, rx: float, tx: float) -> None:
        with self.lock:
            self.timestamps.append(timestamp)
            self.cpu_history.append(cpu)
            self.ram_history.append(ram)
            self.swap_history.append(swap)
            self.net_rx_history.append(rx)
            self.net_tx_history.append(tx)

    def get_snapshots(self) -> Dict[str, List[float]]:
        with self.lock:
            return {
                "timestamps": list(self.timestamps),
                "cpu": list(self.cpu_history),
                "ram": list(self.ram_history),
                "swap": list(self.swap_history),
                "net_rx": list(self.net_rx_history),
                "net_tx": list(self.net_tx_history),
            }


def get_cpu_model_name() -> str:
    """Read CPU model name from /proc/cpuinfo or platform."""
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":", 1)[1].strip()
                elif line.startswith("Model") or line.startswith("Hardware"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"



def get_os_display_name() -> str:
    """Read pretty OS name."""
    try:
        data = platform.freedesktop_os_release()
        return data.get("PRETTY_NAME") or data.get("NAME") or "Arch Linux"
    except Exception:
        return "Linux"


class MetricsCollector:
    """
    Background worker that samples system metrics at a configured cadence.
    Uses non-blocking accessors for GTK UI threads.
    """

    def __init__(self, interval_ms: int = 1000, history_points: int = 60, preferred_net_iface: str = "auto") -> None:
        self.interval_sec = max(0.5, interval_ms / 1000.0)
        self.history_points = history_points
        self.preferred_net_iface = preferred_net_iface

        self.history = MetricsHistory(maxlen=history_points)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._last_net_io: Dict[str, Tuple[int, int]] = {}
        self._last_net_time: float = 0.0

        # Cached static system info
        self._cpu_model = get_cpu_model_name()
        self._os_name = get_os_display_name()
        self._kernel = platform.release()
        self._hostname = platform.node()
        self._cpu_arch = platform.machine()
        self._logical_cores = psutil.cpu_count(logical=True) or 1
        self._physical_cores = psutil.cpu_count(logical=False) or self._logical_cores

        # Initial sample to prime psutil counters
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception:
            pass

        self._latest_snapshot = SystemSnapshot()
        self._sample()

    def set_interval_ms(self, interval_ms: int) -> None:
        self.interval_sec = max(0.5, interval_ms / 1000.0)

    def set_history_points(self, points: int) -> None:
        self.history_points = points
        self.history.set_maxlen(points)

    def set_preferred_interface(self, iface: str) -> None:
        self.preferred_net_iface = iface

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="SysPulseCollector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                self._sample()
            except Exception:
                # Reliability guarantee: never let an unexpected exception kill the collector loop
                pass
            elapsed = time.time() - t0
            sleep_time = max(0.05, self.interval_sec - elapsed)
            self._stop_event.wait(sleep_time)

    def _sample(self) -> None:
        now = time.time()

        # 1. CPU Metrics
        try:
            cpu_total = float(psutil.cpu_percent(interval=None))
            per_core = [float(p) for p in psutil.cpu_percent(interval=None, percpu=True)]
            freq = 0.0
            try:
                freq_info = psutil.cpu_freq()
                if freq_info and hasattr(freq_info, "current") and freq_info.current is not None:
                    freq = float(freq_info.current)
            except Exception:
                freq = 0.0
            cpu_snap = CpuSnapshot(
                total_percent=cpu_total,
                per_core=per_core,
                logical_cores=self._logical_cores,
                physical_cores=self._physical_cores,
                frequency_mhz=freq,
            )
        except Exception:
            cpu_snap = CpuSnapshot(
                total_percent=0.0,
                per_core=[],
                logical_cores=self._logical_cores,
                physical_cores=self._physical_cores,
                frequency_mhz=0.0,
            )

        # 2. Memory Metrics
        try:
            vmem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            mem_snap = MemorySnapshot(
                total_bytes=vmem.total,
                used_bytes=vmem.used,
                available_bytes=vmem.available,
                percent=float(vmem.percent),
                swap_total_bytes=swap.total,
                swap_used_bytes=swap.used,
                swap_percent=float(swap.percent),
            )
        except Exception:
            mem_snap = MemorySnapshot()

        # 3. Disks Metrics
        disks: List[DiskPartitionSnapshot] = []
        try:
            partitions = psutil.disk_partitions(all=False)
            seen_mounts = set()
            for p in partitions:
                # Filter virtual or pseudo filesystems
                if p.mountpoint in seen_mounts:
                    continue
                if p.fstype in ("squashfs", "overlay", "iso9660") or p.mountpoint.startswith("/var/lib/docker"):
                    continue
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    disks.append(
                        DiskPartitionSnapshot(
                            device=p.device,
                            mountpoint=p.mountpoint,
                            fstype=p.fstype,
                            total_bytes=usage.total,
                            used_bytes=usage.used,
                            free_bytes=usage.free,
                            percent=float(usage.percent),
                        )
                    )
                    seen_mounts.add(p.mountpoint)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except Exception:
            pass

        # 4. Networking Metrics
        net_snap = self._sample_network(now)

        # 5. Sensors (Graceful fallback)
        sensor_snap = self._sample_sensors()

        # 6. System Info
        uptime = 0.0
        try:
            uptime = max(0.0, now - psutil.boot_time())
        except Exception:
            pass

        load_avg = (0.0, 0.0, 0.0)
        try:
            load_avg = os.getloadavg()
        except Exception:
            pass

        sys_info = SystemInfo(
            hostname=self._hostname,
            os_name=self._os_name,
            kernel=self._kernel,
            cpu_model=self._cpu_model,
            cpu_arch=self._cpu_arch,
            total_memory_bytes=mem_snap.total_bytes,
            uptime_seconds=uptime,
            load_avg=load_avg,
        )

        # 7. Processes
        processes = self._sample_processes()

        snapshot = SystemSnapshot(
            timestamp=now,
            cpu=cpu_snap,
            memory=mem_snap,
            disks=disks,
            network=net_snap,
            sensors=sensor_snap,
            sys_info=sys_info,
            processes=processes,
        )

        # Update History
        self.history.append(
            timestamp=now,
            cpu=cpu_snap.total_percent,
            ram=mem_snap.percent,
            swap=mem_snap.swap_percent,
            rx=net_snap.rx_rate,
            tx=net_snap.tx_rate,
        )

        with self._lock:
            self._latest_snapshot = snapshot

    def _sample_network(self, now: float) -> NetworkSnapshot:
        interfaces: Dict[str, NetworkInterfaceSnapshot] = {}
        total_rx_rate = 0.0
        total_tx_rate = 0.0
        total_rx_bytes = 0
        total_tx_bytes = 0

        dt = now - self._last_net_time if self._last_net_time > 0 else 0.0
        self._last_net_time = now

        try:
            io_counters = psutil.net_io_counters(pernic=True)
            stats = psutil.net_if_stats()
        except Exception:
            io_counters = {}
            stats = {}

        for iface_name, io in io_counters.items():
            is_up = stats[iface_name].isup if iface_name in stats else True
            rx_bytes = io.bytes_recv
            tx_bytes = io.bytes_sent

            rx_rate = 0.0
            tx_rate = 0.0
            if dt > 0 and iface_name in self._last_net_io:
                last_rx, last_tx = self._last_net_io[iface_name]
                if rx_bytes >= last_rx:
                    rx_rate = (rx_bytes - last_rx) / dt
                if tx_bytes >= last_tx:
                    tx_rate = (tx_bytes - last_tx) / dt

            self._last_net_io[iface_name] = (rx_bytes, tx_bytes)

            # Ignore loopback for aggregate rates
            if iface_name != "lo" and not iface_name.startswith("vmnet"):
                total_rx_rate += rx_rate
                total_tx_rate += tx_rate
                total_rx_bytes += rx_bytes
                total_tx_bytes += tx_bytes

            interfaces[iface_name] = NetworkInterfaceSnapshot(
                name=iface_name,
                rx_bytes_sec=rx_rate,
                tx_bytes_sec=tx_rate,
                rx_total_bytes=rx_bytes,
                tx_total_bytes=tx_bytes,
                is_up=is_up,
            )

        active = self.preferred_net_iface
        if active != "auto" and active in interfaces:
            target_rx_rate = interfaces[active].rx_bytes_sec
            target_tx_rate = interfaces[active].tx_bytes_sec
            target_rx_bytes = interfaces[active].rx_total_bytes
            target_tx_bytes = interfaces[active].tx_total_bytes
        else:
            # Find default / most active non-loopback interface
            target_rx_rate = total_rx_rate
            target_tx_rate = total_tx_rate
            target_rx_bytes = total_rx_bytes
            target_tx_bytes = total_tx_bytes

        return NetworkSnapshot(
            interfaces=interfaces,
            active_interface=active,
            rx_rate=target_rx_rate,
            tx_rate=target_tx_rate,
            rx_total=target_rx_bytes,
            tx_total=target_tx_bytes,
        )

    def _sample_sensors(self) -> SensorSnapshot:
        temperatures: List[SensorDevice] = []
        cpu_temp: Optional[float] = None
        fans: List[Tuple[str, int]] = []

        try:
            temps = psutil.sensors_temperatures()
        except Exception:
            temps = {}

        if temps:
            for chip_name, entries in temps.items():
                for entry in entries:
                    label = entry.label if entry.label else chip_name
                    val = float(entry.current)
                    temperatures.append(
                        SensorDevice(
                            name=chip_name,
                            label=label,
                            current_value=val,
                            high_value=entry.high,
                            critical_value=entry.critical,
                            unit="°C",
                        )
                    )
                    # Pick CPU temp
                    if cpu_temp is None:
                        lower_chip = chip_name.lower()
                        lower_label = label.lower()
                        if any(k in lower_chip for k in ("k10temp", "coretemp", "cpu")) or any(
                            k in lower_label for k in ("tctl", "die", "package", "cpu")
                        ):
                            cpu_temp = val

            # If no explicit CPU match was tagged, pick the first valid sensor
            if cpu_temp is None and temperatures:
                cpu_temp = temperatures[0].current_value
        else:
            # Fallback to direct /sys/class/thermal inspection
            sys_cpu_temp = self._read_sysfs_cpu_temp()
            if sys_cpu_temp is not None:
                cpu_temp = sys_cpu_temp
                temperatures.append(
                    SensorDevice(
                        name="thermal_zone",
                        label="Thermal Zone",
                        current_value=cpu_temp,
                    )
                )

        try:
            fan_func = getattr(psutil, "sensors_fans", None)
            if callable(fan_func):
                fan_dict = fan_func()
                if fan_dict and isinstance(fan_dict, dict):
                    for chip, fan_list in fan_dict.items():
                        for f in fan_list:
                            lbl = getattr(f, "label", None) or chip
                            current_rpm = getattr(f, "current", 0)
                            fans.append((lbl, int(current_rpm)))
        except Exception:
            pass

        return SensorSnapshot(cpu_temp=cpu_temp, temperatures=temperatures, fans=fans)

    def _read_sysfs_cpu_temp(self) -> Optional[float]:
        try:
            base = Path("/sys/class/thermal")
            if not base.exists():
                return None
            for zone in base.glob("thermal_zone*"):
                try:
                    temp_file = zone / "temp"
                    if temp_file.is_file():
                        with open(temp_file, "r", encoding="utf-8") as f:
                            raw = f.read().strip()
                            val = float(raw) / 1000.0
                            if 10.0 <= val <= 115.0:
                                return round(val, 1)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _sample_processes(self) -> List[ProcessItem]:
        procs: List[ProcessItem] = []
        attrs = ["pid", "name", "username", "cpu_percent", "memory_percent", "memory_info", "status"]
        try:
            for p in psutil.process_iter(attrs):
                try:
                    info = p.info
                    pid = info.get("pid") or 0
                    if pid == 0:
                        continue
                    name = info.get("name") or "unknown"
                    username = info.get("username") or "user"
                    cpu = float(info.get("cpu_percent") or 0.0)
                    mem_pct = float(info.get("memory_percent") or 0.0)
                    mem_info = info.get("memory_info")
                    rss = mem_info.rss if mem_info else 0
                    status = str(info.get("status") or "")

                    procs.append(
                        ProcessItem(
                            pid=pid,
                            name=name,
                            username=username,
                            cpu_percent=cpu,
                            memory_percent=mem_pct,
                            memory_rss=rss,
                            status=status,
                        )
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.Error, Exception):
                    continue
        except Exception:
            pass

        # Sort descending by CPU by default
        procs.sort(key=lambda x: x.cpu_percent, reverse=True)
        return procs

    def get_snapshot(self) -> SystemSnapshot:
        with self._lock:
            return self._latest_snapshot

    def get_history(self) -> Dict[str, List[float]]:
        return self.history.get_snapshots()


def terminate_process(pid: int, force: bool = False) -> Tuple[bool, str]:
    """
    Safely send SIGTERM or SIGKILL to a process with full error handling.
    """
    try:
        proc = psutil.Process(pid)
        if force:
            proc.kill()
            return True, f"Sent SIGKILL to process {pid} ({proc.name()})"
        else:
            proc.terminate()
            return True, f"Sent SIGTERM to process {pid} ({proc.name()})"
    except psutil.NoSuchProcess:
        return False, f"Process {pid} no longer exists."
    except psutil.AccessDenied:
        return False, f"Permission denied to terminate process {pid}. (Process may belong to another user or root)"
    except Exception as e:
        return False, f"Failed to terminate process {pid}: {e}"
