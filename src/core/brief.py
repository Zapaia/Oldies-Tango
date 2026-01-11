from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Brief:
    title: str
    mood: str
    era: str
    ambience: str
    duration_sec: int
    audio_notes: str
    visual_notes: str
    notes: str
