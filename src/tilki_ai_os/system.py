from __future__ import annotations

import os
import platform
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SystemStatus:
    os: str
    kernel: str
    machine: str
    python: str
    cpu_count: int
    load_1m: float | None
    memory_total_gb: float | None
    memory_available_gb: float | None


def _memory_linux() -> tuple[float | None, float | None]:
    try:
        values: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, raw = line.split(":", 1)
                if key in {"MemTotal", "MemAvailable"}:
                    values[key] = int(raw.strip().split()[0])
        scale = 1024 * 1024
        return values.get("MemTotal", 0) / scale, values.get("MemAvailable", 0) / scale
    except (OSError, ValueError):
        return None, None


def get_system_status() -> SystemStatus:
    try:
        load = os.getloadavg()[0]
    except (AttributeError, OSError):
        load = None

    total, available = _memory_linux() if platform.system() == "Linux" else (None, None)
    return SystemStatus(
        os=platform.system(),
        kernel=platform.release(),
        machine=platform.machine(),
        python=platform.python_version(),
        cpu_count=os.cpu_count() or 1,
        load_1m=load,
        memory_total_gb=total,
        memory_available_gb=available,
    )


def status_dict() -> dict[str, object]:
    return asdict(get_system_status())
