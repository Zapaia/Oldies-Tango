from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Brief:
    title: str
    mood: str
    era: str
    ambience: str
    duration_sec: int
    audio_notes: str
    visual_notes: str
    audio_fx: list[str] = field(default_factory=list)
    iconic_figure: str = ""
    image_text: str = ""
    animatable_elements: list[str] = field(default_factory=list)
    dalle_prompt: str = ""
    music_search_query: str = ""
    music_search_artist: str = ""
    music_search_style: str = ""
    notes: str = ""
