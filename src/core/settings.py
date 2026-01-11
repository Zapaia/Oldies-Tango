from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectSettings:
    name: str
    default_duration_sec: int


@dataclass(frozen=True)
class PathsSettings:
    runs_dir: str


@dataclass(frozen=True)
class PipelineSettings:
    project: ProjectSettings
    paths: PathsSettings


@dataclass(frozen=True)
class PromptBundle:
    creative_director: str
    visual: str
    music: str
    metadata: str


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_pipeline_settings(config_path: str = "configs/pipeline.yaml") -> PipelineSettings:
    data = load_yaml(Path(config_path))
    project = ProjectSettings(
        name=data["project"]["name"],
        default_duration_sec=int(data["project"]["default_duration_sec"]),
    )
    paths = PathsSettings(runs_dir=data["paths"]["runs_dir"])
    return PipelineSettings(project=project, paths=paths)


def load_prompts(base_dir: str = "configs/prompts") -> PromptBundle:
    base = Path(base_dir)
    return PromptBundle(
        creative_director=base.joinpath("creative_director.md").read_text(encoding="utf-8"),
        visual=base.joinpath("visual.md").read_text(encoding="utf-8"),
        music=base.joinpath("music.md").read_text(encoding="utf-8"),
        metadata=base.joinpath("metadata.md").read_text(encoding="utf-8"),
    )
