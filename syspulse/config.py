"""
SysPulse Configuration Module
Handles persistent configuration in ~/.config/syspulse/config.json with safe defaults and validation.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class Config:
    refresh_interval_ms: int = 1000
    history_points: int = 60
    preferred_interface: str = "auto"
    temperature_unit: str = "C"
    theme: str = "dark"
    show_per_core: bool = True

    def validate(self) -> None:
        """Sanitize and clamp values to safe operational ranges."""
        if not isinstance(self.refresh_interval_ms, (int, float)):
            self.refresh_interval_ms = 1000
        self.refresh_interval_ms = int(max(500, min(10000, self.refresh_interval_ms)))

        if not isinstance(self.history_points, int):
            self.history_points = 60
        self.history_points = max(20, min(300, self.history_points))

        if not isinstance(self.preferred_interface, str):
            self.preferred_interface = "auto"

        if self.temperature_unit not in ("C", "F"):
            self.temperature_unit = "C"

        if self.theme not in ("dark", "light", "system"):
            self.theme = "dark"

        if not isinstance(self.show_per_core, bool):
            self.show_per_core = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Config:
        valid_keys = {k for k in cls.__dataclass_fields__.keys()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        cfg = cls(**filtered)
        cfg.validate()
        return cfg


def get_config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    return base / "syspulse" / "config.json"


def load_config() -> Config:
    """Load config from disk or return validated defaults."""
    path = get_config_path()
    if not path.is_file():
        cfg = Config()
        return cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return Config.from_dict(data)
    except Exception:
        pass

    return Config()


def save_config(cfg: Config) -> bool:
    """Save config to disk securely."""
    cfg.validate()
    path = get_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        temp_path.replace(path)
        return True
    except Exception:
        return False
