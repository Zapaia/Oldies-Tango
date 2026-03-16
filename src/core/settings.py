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
class MusicSettings:
    source_mode: str  # "public_domain" | "ai_generated"


@dataclass(frozen=True)
class ImageSettings:
    source_mode: str  # "api" | "manual"


@dataclass(frozen=True)
class YoutubeSettings:
    privacy_status: str  # "private" | "unlisted" | "public"


@dataclass(frozen=True)
class NotificationsSettings:
    enabled: bool
    to_email: str
    smtp_host: str
    smtp_port: int


@dataclass(frozen=True)
class ChannelSettings:
    cafecito_url: str  # "" = no incluir en descripciones


@dataclass(frozen=True)
class CompilationSettings:
    target_duration_min: int   # minutos mínimos de videos limpios para compilar
    auto_trigger: bool         # compilar automáticamente luego de cada run exitoso
    privacy_status: str        # "private" | "unlisted" | "public"


@dataclass(frozen=True)
class PipelineSettings:
    project: ProjectSettings
    paths: PathsSettings
    music: MusicSettings
    image: ImageSettings
    youtube: YoutubeSettings
    notifications: NotificationsSettings
    compilation: CompilationSettings
    channel: ChannelSettings


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
    music_data = data.get("music", {})
    music = MusicSettings(
        source_mode=music_data.get("source_mode", "public_domain"),
    )
    image_data = data.get("image", {})
    image = ImageSettings(
        source_mode=image_data.get("source_mode", "manual"),
    )
    youtube_data = data.get("youtube", {})
    youtube = YoutubeSettings(
        privacy_status=youtube_data.get("privacy_status", "private"),
    )
    notif_data = data.get("notifications", {})
    notifications = NotificationsSettings(
        enabled=notif_data.get("enabled", False),
        to_email=notif_data.get("to_email", ""),
        smtp_host=notif_data.get("smtp_host", "smtp.gmail.com"),
        smtp_port=int(notif_data.get("smtp_port", 587)),
    )
    comp_data = data.get("compilation", {})
    compilation = CompilationSettings(
        target_duration_min=int(comp_data.get("target_duration_min", 60)),
        auto_trigger=bool(comp_data.get("auto_trigger", False)),
        privacy_status=comp_data.get("privacy_status", "public"),
    )
    channel_data = data.get("channel", {})
    channel = ChannelSettings(
        cafecito_url=channel_data.get("cafecito_url", ""),
    )
    return PipelineSettings(project=project, paths=paths, music=music, image=image, youtube=youtube, notifications=notifications, compilation=compilation, channel=channel)


def load_prompts(base_dir: str = "configs/prompts") -> PromptBundle:
    base = Path(base_dir)
    return PromptBundle(
        creative_director=base.joinpath("creative_director.md").read_text(encoding="utf-8"),
        visual=base.joinpath("visual.md").read_text(encoding="utf-8"),
        music=base.joinpath("music.md").read_text(encoding="utf-8"),
        metadata=base.joinpath("metadata.md").read_text(encoding="utf-8"),
    )
