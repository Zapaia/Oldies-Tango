"""
Módulo de estadísticas del canal YouTube para el email de notificación.
Reutiliza las credenciales OAuth del publisher_agent.

Nota: Si el pipeline falla al obtener stats, retorna un report vacío con el error
      — nunca interrumpe el pipeline principal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from googleapiclient.discovery import build

from src.agents.publisher_agent import _get_credentials


@dataclass
class ChannelStats:
    subscribers: str    # Formateado: "1.2K", "45", "1.0M"
    total_views: str
    video_count: int


@dataclass
class VideoStats:
    video_id: str
    title: str
    views: int
    likes: int
    comments: int
    url: str
    licensed_content: bool = False  # True = ContentID claim activo


@dataclass
class YoutubeReport:
    channel: Optional[ChannelStats] = None
    recent_videos: list[VideoStats] = field(default_factory=list)
    recent_comments: list[dict] = field(default_factory=list)  # {author, text, likes}
    latest_video_id: Optional[str] = None
    error: Optional[str] = None


def fetch_youtube_report(max_videos: int = 5, max_comments: int = 8) -> YoutubeReport:
    """Obtiene stats del canal, últimos videos y comentarios recientes.

    Retorna YoutubeReport con error si algo falla — no lanza excepciones.
    """
    try:
        creds = _get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        # --- 1. Stats del canal ---
        ch_resp = youtube.channels().list(part="statistics", mine=True).execute()
        ch_stats = None
        if ch_resp.get("items"):
            s = ch_resp["items"][0]["statistics"]
            ch_stats = ChannelStats(
                subscribers=_fmt(int(s.get("subscriberCount", 0))),
                total_views=_fmt(int(s.get("viewCount", 0))),
                video_count=int(s.get("videoCount", 0)),
            )

        # --- 2. IDs de los últimos videos ---
        search_resp = youtube.search().list(
            part="snippet",
            forMine=True,
            type="video",
            order="date",
            maxResults=max_videos,
        ).execute()
        video_ids = [item["id"]["videoId"] for item in search_resp.get("items", [])]
        latest_video_id = video_ids[0] if video_ids else None

        # --- 3. Stats detalladas de esos videos (incluye ContentID check) ---
        recent_videos: list[VideoStats] = []
        if video_ids:
            stats_resp = youtube.videos().list(
                part="statistics,snippet,contentDetails",
                id=",".join(video_ids),
            ).execute()
            for item in stats_resp.get("items", []):
                s = item.get("statistics", {})
                cd = item.get("contentDetails", {})
                recent_videos.append(VideoStats(
                    video_id=item["id"],
                    title=item["snippet"]["title"],
                    views=int(s.get("viewCount", 0)),
                    likes=int(s.get("likeCount", 0)),
                    comments=int(s.get("commentCount", 0)),
                    url=f"https://youtu.be/{item['id']}",
                    licensed_content=cd.get("licensedContent", False),
                ))

        # --- 4. Comentarios del video más reciente ---
        recent_comments: list[dict] = []
        if latest_video_id:
            try:
                comments_resp = youtube.commentThreads().list(
                    part="snippet",
                    videoId=latest_video_id,
                    order="time",
                    maxResults=max_comments,
                ).execute()
                for item in comments_resp.get("items", []):
                    top = item["snippet"]["topLevelComment"]["snippet"]
                    recent_comments.append({
                        "author": top["authorDisplayName"],
                        "text": top["textOriginal"][:250].replace("<", "&lt;").replace(">", "&gt;"),
                        "likes": int(top.get("likeCount", 0)),
                    })
            except Exception:
                pass  # Comentarios deshabilitados o sin permisos — no crítico

        return YoutubeReport(
            channel=ch_stats,
            recent_videos=recent_videos,
            recent_comments=recent_comments,
            latest_video_id=latest_video_id,
        )

    except Exception as e:
        return YoutubeReport(error=str(e))


def _fmt(n: int) -> str:
    """Formatea números grandes: 1234567 → '1.2M', 45000 → '45.0K'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
