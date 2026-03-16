"""
compile_videos.py — Crea compilaciones de ~1hr con los mejores videos de Oldies Tango.

Flujo:
1. Escanea data/runs/ para encontrar videos subidos a YouTube
2. Verifica estado en YouTube API: descarta bloqueados/eliminados por copyright
3. Si los videos limpios y no usados suman >= target_duration_min, crea la compilación
4. Concatena los videos localmente (corte directo, sin transición)
5. Genera thumbnail mosaico con imágenes de los videos incluidos
6. Genera metadata con tracklist y descripción del canal
7. Sube a YouTube si --upload

Uso:
    python -m src.pipelines.compile_videos
    python -m src.pipelines.compile_videos --upload
    python -m src.pipelines.compile_videos --check    # solo verifica si hay suficientes videos
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from moviepy import VideoFileClip, concatenate_videoclips

from src.agents.publisher_agent import _get_credentials
from src.core.settings import load_pipeline_settings

COMPILATIONS_DIR = Path("data/compilations")
HISTORY_FILE = COMPILATIONS_DIR / "history.json"


# ─── Historial ────────────────────────────────────────────────────────────────

def _load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {"compilations": [], "used_video_ids": []}


def _save_history(history: dict) -> None:
    COMPILATIONS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ─── Escaneo de runs ──────────────────────────────────────────────────────────

def _scan_uploaded_runs(runs_dir: Path) -> list[dict]:
    """Retorna info de todos los runs que fueron subidos a YouTube (tienen upload_result.json)."""
    results = []
    for run_path in sorted(runs_dir.glob("run-*/")):
        upload_file = run_path / "upload_result.json"
        video_file = run_path / "video.mp4"
        if not upload_file.exists() or not video_file.exists():
            continue
        try:
            upload_data = json.loads(upload_file.read_text(encoding="utf-8"))
            video_id = upload_data.get("video_id", "")
            if not video_id:
                continue

            # Título del video (para tracklist)
            music_title, music_artist = "", ""
            music_file = run_path / "music_result.json"
            if music_file.exists():
                music_data = json.loads(music_file.read_text(encoding="utf-8"))
                music_title = music_data.get("title", "")
                music_artist = music_data.get("artist", "")

            yt_title = ""
            metadata_file = run_path / "metadata.json"
            if metadata_file.exists():
                yt_title = json.loads(metadata_file.read_text(encoding="utf-8")).get("title", "")

            thumbnail_path = run_path / "thumbnail.jpg"
            results.append({
                "run_dir": run_path,
                "video_id": video_id,
                "video_path": video_file,
                "thumbnail_path": thumbnail_path if thumbnail_path.exists() else None,
                "music_title": music_title,
                "music_artist": music_artist,
                "yt_title": yt_title,
                "run_name": run_path.name,
            })
        except Exception:
            continue

    return results


# ─── Verificación de estado en YouTube ───────────────────────────────────────

def _check_videos_status(youtube, video_ids: list[str]) -> dict[str, bool]:
    """
    Retorna {video_id: is_clean} para cada ID.

    is_clean = True SOLO si:
    - uploadStatus == "processed" (no bloqueado/eliminado)
    - privacyStatus == "public"
    - licensedContent == False (sin reclamación ContentID de ningún tipo)

    Videos no encontrados = eliminados o bloqueados globalmente → False.
    Videos monitoreados por ContentID (licensedContent=True) → False.
    """
    result = {vid: False for vid in video_ids}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            resp = youtube.videos().list(
                part="status,contentDetails", id=",".join(batch)
            ).execute()
            found_ids = set()
            for item in resp.get("items", []):
                vid_id = item["id"]
                found_ids.add(vid_id)
                s = item.get("status", {})
                cd = item.get("contentDetails", {})
                result[vid_id] = (
                    s.get("uploadStatus") == "processed"
                    and s.get("privacyStatus") == "public"
                    and not cd.get("licensedContent", False)
                )
            # Los no encontrados quedan en False (eliminados/bloqueados)
        except Exception as e:
            print(f"[compiler] Advertencia al verificar estado: {e}")
    return result


# ─── Duración ─────────────────────────────────────────────────────────────────

def _get_video_duration(video_path: Path) -> float:
    try:
        with VideoFileClip(str(video_path)) as clip:
            return clip.duration
    except Exception:
        return 180.0  # fallback: 3 minutos


# ─── Lógica principal ─────────────────────────────────────────────────────────

def get_compilable_videos(
    runs_dir: Path,
    target_duration_sec: float = 3600.0,
) -> tuple[list[dict], float]:
    """
    Retorna (videos_elegibles, duracion_total_segundos).

    Elegibles = subidos a YouTube + públicos + sin bloqueo + no usados en compilaciones anteriores.
    """
    history = _load_history()
    used_ids = set(history.get("used_video_ids", []))

    runs = _scan_uploaded_runs(runs_dir)
    runs = [r for r in runs if r["video_id"] not in used_ids]

    if not runs:
        return [], 0.0

    try:
        creds = _get_credentials()
        youtube = build("youtube", "v3", credentials=creds)
        status_map = _check_videos_status(youtube, [r["video_id"] for r in runs])
    except Exception as e:
        print(f"[compiler] No se pudo verificar YouTube API: {e}")
        return [], 0.0

    clean = [r for r in runs if status_map.get(r["video_id"], False)]

    total = 0.0
    for r in clean:
        r["duration_sec"] = _get_video_duration(r["video_path"])
        total += r["duration_sec"]

    return clean, total


def should_compile(runs_dir: Path, target_duration_sec: float = 3600.0) -> bool:
    """True si hay suficientes videos limpios para una compilación."""
    _, total = get_compilable_videos(runs_dir, target_duration_sec)
    return total >= target_duration_sec


# ─── Generación de metadata ───────────────────────────────────────────────────

def _build_metadata(selected: list[dict], vol_num: int, total_sec: float) -> dict:
    duration_hours = total_sec / 3600
    duration_str = "1 Hour" if duration_hours < 1.1 else f"{duration_hours:.1f} Hours"
    title = (
        f"{duration_str} Vintage Tango 🎷 Argentine Classics Mix Vol. {vol_num} | Oldies Tango"
    )

    # Tracklist con timestamps
    tracklist_lines = []
    cursor = 0
    for r in selected:
        mins = int(cursor) // 60
        secs = int(cursor) % 60
        track_name = r["music_title"] or r["yt_title"] or r["run_name"]
        artist = f" — {r['music_artist']}" if r["music_artist"] else ""
        tracklist_lines.append(f"{mins:02d}:{secs:02d}  {track_name}{artist}")
        cursor += r.get("duration_sec", 180.0)

    tracklist = "\n".join(tracklist_lines)

    description = (
        f"The best vintage Argentine tango — curated and compiled for your listening pleasure.\n\n"
        f"🎵 TRACKLIST\n{tracklist}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎹 Oldies Tango — Argentine classics from the golden age of tango.\n"
        f"All music is in the public domain (pre-1930 recordings).\n\n"
        f"Subscribe for daily tango videos → https://www.youtube.com/@OldiesTango\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"#tango #argentino #tangoclasico #musica #oldies #vintage #lofi #asmr"
    )

    tags = [
        "tango", "tango argentino", "Argentine tango", "vintage tango",
        "tango compilation", "1 hour tango", "tango mix", "best of tango",
        "oldies tango", "Carlos Gardel", "Francisco Canaro", "Anibal Troilo",
        "tango playlist", "tango clasico", "musica argentina",
    ]

    return {"title": title, "description": description, "tags": tags, "category": "Music"}


# ─── Compilar ─────────────────────────────────────────────────────────────────

def compile_videos(
    runs_dir: Path,
    target_duration_sec: float = 3600.0,
    privacy_status: str = "public",
    upload: bool = False,
) -> Path:
    """
    Crea una compilación de 1hr+ con los videos limpios disponibles.

    Returns: Path a la carpeta de la compilación generada.
    Raises: ValueError si no hay suficientes videos limpios.
    """
    print("[compiler] Iniciando compilación...")
    COMPILATIONS_DIR.mkdir(parents=True, exist_ok=True)
    history = _load_history()

    clean_runs, total_sec = get_compilable_videos(runs_dir, target_duration_sec)

    if total_sec < target_duration_sec:
        mins_have = total_sec / 60
        mins_need = target_duration_sec / 60
        raise ValueError(
            f"Videos limpios suman {mins_have:.1f} min — mínimo {mins_need:.0f} min. "
            f"Faltan {(mins_need - mins_have):.1f} min más."
        )

    # Seleccionar en orden cronológico hasta completar la hora
    selected: list[dict] = []
    accumulated = 0.0
    for r in clean_runs:
        selected.append(r)
        accumulated += r["duration_sec"]
        if accumulated >= target_duration_sec:
            break

    print(f"[compiler] {len(selected)} videos seleccionados ({accumulated / 60:.1f} min)")

    # Directorio de salida
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    comp_dir = COMPILATIONS_DIR / f"compilation-{timestamp}"
    comp_dir.mkdir(parents=True, exist_ok=True)

    vol_num = len(history.get("compilations", [])) + 1

    # --- Concatenar videos ---
    print("[compiler] Concatenando videos (puede tardar varios minutos)...")
    output_video = comp_dir / "compilation.mp4"
    clips = [VideoFileClip(str(r["video_path"])) for r in selected]
    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip.write_videofile(
        str(output_video), codec="libx264", audio_codec="aac", logger=None
    )
    for c in clips:
        c.close()
    final_clip.close()
    print(f"[compiler] Video listo: {output_video}")

    # --- Thumbnail mosaico ---
    from src.media.image.mosaic import create_mosaic
    thumb_paths = [r["thumbnail_path"] for r in selected if r["thumbnail_path"]]
    output_thumbnail = comp_dir / "thumbnail.jpg"
    create_mosaic(thumb_paths, output_thumbnail)
    print(f"[compiler] Thumbnail: {output_thumbnail}")

    # --- Metadata ---
    metadata = _build_metadata(selected, vol_num, accumulated)
    metadata_path = comp_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[compiler] Metadata: {metadata['title']}")

    # --- Info de la compilación ---
    comp_info = {
        "vol": vol_num,
        "timestamp": timestamp,
        "title": metadata["title"],
        "duration_sec": accumulated,
        "video_count": len(selected),
        "video_ids": [r["video_id"] for r in selected],
        "run_dirs": [str(r["run_dir"]) for r in selected],
        "comp_dir": str(comp_dir),
        "youtube_url": None,
    }
    (comp_dir / "compilation_info.json").write_text(
        json.dumps(comp_info, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- Subir a YouTube ---
    if upload:
        print("[compiler] Subiendo compilación a YouTube...")
        creds = _get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        request_body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"],
                "categoryId": "10",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(str(output_video), mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=request_body, media_body=media
        )

        response = None
        while response is None:
            status_up, response = request.next_chunk()
            if status_up:
                print(f"[compiler] Upload: {int(status_up.progress() * 100)}%")

        video_id = response["id"]
        youtube_url = f"https://youtu.be/{video_id}"
        print(f"[compiler] Compilación subida: {youtube_url}")

        if output_thumbnail.exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(output_thumbnail)),
                ).execute()
            except Exception:
                pass

        comp_info["youtube_url"] = youtube_url
        comp_info["youtube_video_id"] = video_id
        (comp_dir / "upload_result.json").write_text(
            json.dumps({"video_id": video_id, "youtube_url": youtube_url}, indent=2),
            encoding="utf-8",
        )
        (comp_dir / "compilation_info.json").write_text(
            json.dumps(comp_info, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # --- Actualizar historial ---
    history.setdefault("compilations", []).append(comp_info)
    used_ids: list[str] = history.get("used_video_ids", [])
    for r in selected:
        if r["video_id"] not in used_ids:
            used_ids.append(r["video_id"])
    history["used_video_ids"] = used_ids
    _save_history(history)

    print(f"[compiler] Compilación guardada en: {comp_dir}")
    return comp_dir


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compilación de videos Oldies Tango")
    parser.add_argument("--upload", action="store_true", help="Subir compilación a YouTube")
    parser.add_argument("--check", action="store_true", help="Solo verificar si hay videos suficientes")
    args = parser.parse_args()

    settings = load_pipeline_settings()
    runs_dir = Path(settings.paths.runs_dir)
    target_sec = settings.compilation.target_duration_min * 60

    if args.check:
        clean, total = get_compilable_videos(runs_dir, target_sec)
        print(f"Videos limpios disponibles: {len(clean)}")
        print(f"Duración total: {total / 60:.1f} min")
        print(f"Objetivo: {settings.compilation.target_duration_min} min")
        print(f"{'✅ Listo para compilar' if total >= target_sec else f'⏳ Faltan {(target_sec - total) / 60:.1f} min más'}")
    else:
        compile_videos(
            runs_dir=runs_dir,
            target_duration_sec=target_sec,
            privacy_status=settings.compilation.privacy_status,
            upload=args.upload,
        )
