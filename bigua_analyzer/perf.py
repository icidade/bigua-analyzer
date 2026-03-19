from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import time
from typing import Iterator


class PerformanceRecorder:
    def __init__(self) -> None:
        self._durations: dict[str, float] = defaultdict(float)

    @contextmanager
    def track(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self._durations[name] += time.perf_counter() - start

    def add_seconds(self, name: str, duration_seconds: float) -> None:
        self._durations[name] += max(0.0, float(duration_seconds))

    def snapshot_ms(self) -> dict[str, float]:
        return {
            name: round(duration * 1000.0, 3)
            for name, duration in sorted(self._durations.items())
        }