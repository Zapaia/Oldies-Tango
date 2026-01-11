from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.core.brief import Brief
from src.core.settings import PromptBundle


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_brief(path: Path, brief: Brief) -> None:
    write_json(path, asdict(brief))


def write_prompt_bundle(path: Path, prompts: PromptBundle) -> None:
    write_json(path, {
        "creative_director": prompts.creative_director.strip(),
        "visual": prompts.visual.strip(),
        "music": prompts.music.strip(),
        "metadata": prompts.metadata.strip(),
    })
