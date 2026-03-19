from __future__ import annotations

import time


def format_duration(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_elapsed(start_time: float) -> str:
    elapsed_seconds = max(0, int(time.time() - start_time))
    return format_duration(elapsed_seconds)


def estimate_eta(start_time: float, completed: int, total: int) -> str | None:
    if completed <= 0 or total <= completed:
        return None

    elapsed_seconds = max(1, int(time.time() - start_time))
    average_seconds_per_item = elapsed_seconds / completed
    remaining_seconds = int(round((total - completed) * average_seconds_per_item))
    return format_duration(remaining_seconds)