"""
SysPulse Formatting and System Utilities
"""

from __future__ import annotations

from typing import Tuple


def format_bytes(bytes_val: float | int, rate: bool = False) -> str:
    """Format bytes into human-readable units (B, KiB, MiB, GiB, TiB)."""
    if bytes_val < 0:
        bytes_val = 0
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    suffix = "/s" if rate else ""
    val = float(bytes_val)
    unit_idx = 0
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(val)} {units[unit_idx]}{suffix}"
    elif val >= 100.0:
        return f"{val:.1f} {units[unit_idx]}{suffix}"
    else:
        return f"{val:.2f} {units[unit_idx]}{suffix}"


def format_uptime(seconds: float) -> str:
    """Format uptime seconds into 'X days, HH:MM:SS' or 'HH:MM:SS'."""
    sec = int(max(0, seconds))
    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds_int = divmod(rem, 60)

    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    elif hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds_int:02d}s"
    else:
        return f"{minutes:02d}m {seconds_int:02d}s"


def format_percentage(pct: float) -> str:
    """Format percentage value."""
    return f"{max(0.0, min(100.0, pct)):.1f}%"


def format_temperature(celsius: float | None, unit: str = "C") -> str:
    """Format temperature in Celsius or Fahrenheit."""
    if celsius is None:
        return "N/A"
    if unit == "F":
        val = (celsius * 9.0 / 5.0) + 32.0
        return f"{val:.1f} °F"
    return f"{celsius:.1f} °C"
