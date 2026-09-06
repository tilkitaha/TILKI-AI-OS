from __future__ import annotations

import csv
import io
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class GPUInfo:
    index: int
    name: str
    memory_used_mb: int
    memory_total_mb: int
    utilization_percent: int
    temperature_c: int

    @property
    def memory_free_mb(self) -> int:
        return self.memory_total_mb - self.memory_used_mb


def list_nvidia_gpus() -> list[GPUInfo]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=3)
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    gpus: list[GPUInfo] = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) != 6:
            continue
        try:
            gpus.append(
                GPUInfo(
                    index=int(row[0].strip()),
                    name=row[1].strip(),
                    memory_used_mb=int(row[2].strip()),
                    memory_total_mb=int(row[3].strip()),
                    utilization_percent=int(row[4].strip()),
                    temperature_c=int(row[5].strip()),
                )
            )
        except ValueError:
            continue
    return gpus
