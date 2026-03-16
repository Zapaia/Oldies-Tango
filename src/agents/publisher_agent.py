"""publisher_agent.py — Sube video a YouTube con OAuth2.

Flujo OAuth:
- Primera vez: abre el browser para autorizar, guarda token en configs/youtube_token.json
- Siguientes veces: usa el token guardado (auto-refresh)

Requiere: configs/youtube_client_secret.json (descargado de Google Cloud Console)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube"]  # upload + read + comentarios

# YouTube category IDs: https://developers.google.com/youtube/v3/docs/videoCategories
_CATEGORY_MAP = {
    "Music": "10",
    "Entertainment": "24",
    "Film": "1",
    "Education": "27",
}
_DEFAULT_CATEGORY_ID = "10"  # Music
CLIENT_SECRETS_FILE = Path("configs/youtube_client_secret.json")
TOKEN_FILE = Path("configs/youtube_token.json")


@dataclass
class UploadResult:
    video_id: str
    youtube_url: str
    privacy_status: str


def _get_credentials() -> Credentials:
    """Carga token existente o abre browser para autorizar (primera vez)."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                raise FileNotFoundError(
                    f"No se encontró {CLIENT_SECRETS_FILE}. "
                    "Descargá las credenciales OAuth desde Google Cloud Console "
                    "y guardá el JSON como configs/youtube_client_secret.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return creds


def upload_video(run_dir: Path, privacy_status: str = "private") -> UploadResult:
    """Sube video.mp4 + thumbnail.jpg a YouTube usando metadata.json del run_dir.

    Args:
        run_dir: Carpeta del run (ej: data/runs/run-2026-03-02_120000)
        privacy_status: "private" | "unlisted" | "public"

    Returns:
        UploadResult con video_id y URL de YouTube
    """
    video_path = run_dir / "video.mp4"
    thumbnail_path = run_dir / "thumbnail.jpg"
    metadata_path = run_dir / "metadata.json"

    if not video_path.exists():
        raise FileNotFoundError(f"No se encontró video.mp4 en {run_dir}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"No se encontró metadata.json en {run_dir}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    request_body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata.get("tags", []),
            "categoryId": _CATEGORY_MAP.get(str(metadata.get("category", "")), _DEFAULT_CATEGORY_ID),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    print(f"[publisher] Subiendo: {metadata['title']} ({privacy_status})")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[publisher] Progreso: {int(status.progress() * 100)}%")

    video_id = response["id"]
    youtube_url = f"https://youtu.be/{video_id}"
    print(f"[publisher] Video subido: {youtube_url}")

    if thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path)),
            ).execute()
            print("[publisher] Thumbnail subido.")
        except Exception as e:
            print(f"[publisher] Thumbnail omitido (canal no verificado aún): {e}")

    return UploadResult(
        video_id=video_id,
        youtube_url=youtube_url,
        privacy_status=privacy_status,
    )
