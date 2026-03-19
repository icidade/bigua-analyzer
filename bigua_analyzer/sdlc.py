from __future__ import annotations

from typing import Literal

SDLCMode = Literal["auto", "human", "hybrid", "ai"]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def resolve_effective_sdlc_mode(selected_mode: SDLCMode, ai_score: float | None) -> Literal["human", "hybrid", "ai"]:
    if selected_mode != "auto":
        return selected_mode

    score = clamp01(ai_score or 0.0)
    if score < 0.30:
        return "human"
    if score < 0.60:
        return "hybrid"
    return "ai"