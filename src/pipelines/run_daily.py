from __future__ import annotations

import argparse
import traceback as _traceback
from pathlib import Path

from src.core.artifacts import write_brief, write_json, write_prompt_bundle
from src.core.logger import get_logger, log_event
from src.core.settings import load_pipeline_settings, load_prompts
from src.core.storage import prepare_run_dir
from src.core.evaluator import EvaluationError
from src.core.evaluation_log import EvaluationLogger
from src.agents.creative_director import CreativeInputs, create_brief
from src.agents.music_agent import MusicInputs, MusicNotFoundError, MusicResult, resolve_music
from src.agents.metadata_agent import MetadataInputs, MusicInfo, generate_metadata
from src.agents.editor_agent import decide_edit
from src.agents.visual_agent import generate_image as generate_visual_image
from src.agents.publisher_agent import upload_video
from src.media.audio.mixer import mix_audio
from src.media.video.renderer import render_video
from src.media.image.thumbnail import generate_thumbnail
from src.core.notifier import RunSummary, send_run_notification
from src.core.tracer import Tracer


# Configuración de evaluación (valores por defecto)
EVALUATION_ENABLED = True
EVALUATION_THRESHOLD = 0.90
EVALUATION_MAX_ATTEMPTS = 2


def _find_asset(directory: Path, extensions: list[str]) -> Path | None:
    """Busca el primer archivo con alguna de las extensiones dadas."""
    for ext in extensions:
        files = list(directory.glob(f"*{ext}"))
        if files:
            return files[0]
    return None


def run(image_path: Path | None = None, audio_path: Path | None = None, upload: bool = False) -> Path:
    logger = get_logger()
    settings = load_pipeline_settings()
    prompts = load_prompts()
    costs: list[dict] = []

    run_dir = prepare_run_dir(settings.paths.runs_dir)
    tracer = Tracer(trace_id=run_dir.name)
    log_event(logger, stage="init", status="ok", run_dir=str(run_dir))

    _video_title: str | None = None
    _video_description: str | None = None
    _youtube_url: str | None = None
    _thumbnail_path: Path | None = None
    _music_title: str | None = None
    _music_artist: str | None = None
    _music_source: str | None = None
    _image_source: str | None = None
    _upload_failed: bool = False
    _upload_error: str | None = None

    # Inicializar logger de evaluaciones
    eval_logger = EvaluationLogger(run_dir=run_dir) if EVALUATION_ENABLED else None

    try:
        try:
            # --- 1. Creative Director: genera el brief ---
            creative_inputs = CreativeInputs(settings=settings, prompts=prompts)
            with tracer.span("creative_director", model="claude-sonnet-4"):
                brief, brief_eval = create_brief(
                    creative_inputs,
                    max_attempts=EVALUATION_MAX_ATTEMPTS,
                    threshold=EVALUATION_THRESHOLD,
                    evaluation_logger=eval_logger
                )
            cost_cd = 0.006 * (1 if brief_eval.passed else 2)
            costs.append({
                "agent": "creative_director",
                "model": "claude-sonnet-4",
                "est_tokens": 2000 * (1 if brief_eval.passed else 2),
                "est_cost_usd": cost_cd
            })
            tracer.spans[-1].metadata["est_cost_usd"] = cost_cd

            write_brief(run_dir / "brief.json", brief)
            log_event(logger, stage="artifact", status="ok", file="brief.json")

            # --- 2. Music Agent: resuelve música (public_domain o ai_generated) ---
            music_inputs = MusicInputs(brief=brief, settings=settings, prompts=prompts)
            with tracer.span("music_agent") as music_span:
                music_result = resolve_music(music_inputs, evaluation_logger=eval_logger)

            if music_result.source == "public_domain":
                cost_music = 0.0
                costs.append({
                    "agent": "music_agent",
                    "model": "archive.org",
                    "est_tokens": 0,
                    "est_cost_usd": cost_music
                })
            else:
                cost_music = 0.005
                costs.append({
                    "agent": "music_agent",
                    "model": "claude-sonnet-4",
                    "est_tokens": 1500,
                    "est_cost_usd": cost_music
                })
            music_span.metadata.update({"model": music_result.source, "est_cost_usd": cost_music})

        except EvaluationError as e:
            if eval_logger:
                eval_logger.save_to_run_dir()
            log_event(logger, stage="evaluation", status="failed", error=str(e))
            print(f"\n[pipeline] ERROR (evaluacion): {e}")
            print(f"[pipeline] Run parcial guardado en: {run_dir}")
            send_run_notification(RunSummary(
                status="error", run_dir=run_dir,
                error_type="EvaluationError", error_message=str(e),
                agent_costs=costs,
                trace=tracer.to_dict(),
            ), settings)
            raise

        except MusicNotFoundError as e:
            if eval_logger:
                eval_logger.save_to_run_dir()
            log_event(logger, stage="music", status="failed", error=str(e))
            print(f"\n[pipeline] ERROR (musica): {e}")
            print(f"[pipeline] Run parcial guardado en: {run_dir}")
            send_run_notification(RunSummary(
                status="error", run_dir=run_dir,
                error_type="MusicNotFoundError", error_message=str(e),
                agent_costs=costs,
                trace=tracer.to_dict(),
            ), settings)
            raise

        _music_title = music_result.title
        _music_artist = music_result.artist
        _music_source = music_result.source

        # Guardar info de música
        write_json(run_dir / "music_result.json", {
            "source": music_result.source,
            "title": music_result.title,
            "artist": music_result.artist,
            "source_url": music_result.source_url,
            "notes": music_result.notes,
            "suno_prompt": music_result.suno_prompt,
            "style_tags": music_result.style_tags,
            "audio_path": str(music_result.audio_path) if music_result.audio_path else "",
        })
        log_event(logger, stage="artifact", status="ok", file="music_result.json")

        # --- 3. Metadata Agent: genera título, descripción y tags para YouTube ---
        music_info = MusicInfo(
            title=music_result.title,
            artist=music_result.artist,
            source=music_result.source,
            source_url=music_result.source_url,
        )
        metadata_inputs = MetadataInputs(
            brief=brief,
            music_info=music_info,
            settings=settings,
            prompts=prompts,
        )
        with tracer.span("metadata_agent", model="claude-sonnet-4", est_cost_usd=0.005):
            metadata = generate_metadata(metadata_inputs)
        _video_title = metadata.title
        _video_description = metadata.description
        write_json(run_dir / "metadata.json", {
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags,
            "category": metadata.category,
            "notes": metadata.notes,
        })
        log_event(logger, stage="artifact", status="ok", file="metadata.json")
        costs.append({
            "agent": "metadata_agent",
            "model": "claude-sonnet-4",
            "est_tokens": 1500,
            "est_cost_usd": 0.005
        })

        # --- 4. Guardar prompts usados ---
        write_prompt_bundle(run_dir / "prompt_bundle.json", prompts)
        log_event(logger, stage="artifact", status="ok", file="prompt_bundle.json")

        # --- 5. Render: imagen + audio → video ---
        # Imagen: argumento CLI > API (DALL-E 3) > manual (src/media/image/)
        if image_path:
            image = image_path
            _image_source = "manual"
            tracer.skip("visual_agent", reason="imagen manual provista via CLI")
        elif settings.image.source_mode == "api":
            with tracer.span("visual_agent", model="dall-e-3/1792x1024") as visual_span:
                visual_result = generate_visual_image(brief, run_dir)
            image = visual_result.image_path
            _image_source = "api"
            costs.append({
                "agent": "visual_agent",
                "model": "dall-e-3/1792x1024",
                "est_tokens": 0,
                "est_cost_usd": visual_result.cost_usd,
            })
            visual_span.metadata["est_cost_usd"] = visual_result.cost_usd
            log_event(logger, stage="artifact", status="ok", file="image.png")
        else:
            image = _find_asset(Path("src/media/image"), [".png", ".jpg", ".jpeg", ".webp"])
            _image_source = "manual"
            tracer.skip("visual_agent", reason="source_mode no es api")

        # Audio: MusicResult > argumento CLI > data/assets/
        audio = music_result.audio_path or audio_path or _find_asset(Path("data/assets/audio"), [".mp3", ".wav", ".ogg"])

        if image and audio:
            # Aplicar efectos de audio si el brief los pide
            if brief.audio_fx:
                mixed_audio = run_dir / "mixed_audio.wav"
                with tracer.span("mixer", fx=brief.audio_fx):
                    mix_audio(audio, mixed_audio, brief.audio_fx)
                audio = mixed_audio
                log_event(logger, stage="artifact", status="ok", file="mixed_audio.wav")
            else:
                tracer.skip("mixer", reason="brief.audio_fx vacío")

            editor = decide_edit(brief)
            with tracer.span("renderer", fade_duration=editor.fade_duration):
                video_path = render_video(image, audio, run_dir / "video.mp4", fade_duration=editor.fade_duration)
            costs.append({"agent": "renderer", "model": "local", "est_tokens": 0, "est_cost_usd": 0.0})
            log_event(logger, stage="artifact", status="ok", file="video.mp4")

            # Texto ya incluido en image.png por visual_agent cuando source_mode=api
            thumb_text = "" if settings.image.source_mode == "api" else brief.image_text
            generate_thumbnail(image, run_dir / "thumbnail.jpg", text=thumb_text)
            _thumbnail_path = run_dir / "thumbnail.jpg"
            log_event(logger, stage="artifact", status="ok", file="thumbnail.jpg")
        else:
            missing = []
            if not image:
                missing.append("imagen (poner en src/media/image/)")
            if not audio:
                missing.append("audio (poner en data/assets/audio/)")
            print(f"[pipeline] Saltando render - faltan assets: {', '.join(missing)}")
            log_event(logger, stage="render", status="skipped", missing=missing)
            tracer.skip("mixer", reason="assets faltantes")
            tracer.skip("renderer", reason="assets faltantes")

        # --- 6. Guardar evaluaciones ---
        summary = {"total_evaluations": 0}
        if eval_logger:
            eval_logger.save_to_run_dir()
            summary = eval_logger.get_summary()
            log_event(logger, stage="evaluation", status="ok", summary=summary)

        # --- 7. Cost tracking ---
        # Agregar costo de evaluaciones subjetivas (Haiku)
        total_evals = summary.get("total_evaluations", 0)
        eval_cost = 0.0005 * total_evals
        costs.append({
            "agent": "evaluator",
            "model": "claude-haiku-4-5",
            "est_tokens": 500 * total_evals,
            "est_cost_usd": eval_cost
        })

        total_cost = sum(c["est_cost_usd"] for c in costs)
        write_json(run_dir / "costs.json", {"calls": costs, "total_est_usd": total_cost})
        log_event(logger, stage="costs", status="ok", total_est_usd=total_cost)

        # --- 8. Publisher: subir a YouTube (opcional) ---
        if upload:
            try:
                with tracer.span("publisher", privacy_status=settings.youtube.privacy_status):
                    upload_result = upload_video(run_dir, privacy_status=settings.youtube.privacy_status)
                write_json(run_dir / "upload_result.json", {
                    "video_id": upload_result.video_id,
                    "youtube_url": upload_result.youtube_url,
                    "privacy_status": upload_result.privacy_status,
                })
                _youtube_url = upload_result.youtube_url
                log_event(logger, stage="publish", status="ok", youtube_url=upload_result.youtube_url)
            except Exception as e:
                _upload_failed = True
                _upload_error = str(e)
                log_event(logger, stage="publish", status="failed", error=str(e))
                print(f"\n[pipeline] ERROR al subir a YouTube: {e}")
                print("[pipeline] El video fue generado — revisá el error en el email.")
        else:
            tracer.skip("publisher", reason="--upload no especificado")

        # Grilla de evaluaciones en consola
        if eval_logger and eval_logger._evaluations:
            from src.core.evaluation_log import render_grid_text
            try:
                print(render_grid_text(eval_logger._evaluations))
            except UnicodeEncodeError:
                print("[evaluations] Grilla no disponible en esta consola (encoding cp1252)")

        send_run_notification(RunSummary(
            status="success",
            run_dir=run_dir,
            video_title=_video_title,
            video_description=_video_description,
            youtube_url=_youtube_url,
            thumbnail_path=_thumbnail_path,
            total_cost_usd=total_cost,
            agent_costs=costs,
            music_title=_music_title,
            music_artist=_music_artist,
            music_source=_music_source,
            image_source=_image_source,
            upload_failed=_upload_failed,
            upload_error=_upload_error,
            trace=tracer.to_dict(),
            evaluations=eval_logger._evaluations if eval_logger else [],
        ), settings)

        # --- 9. Guardar trace ---
        trace_path = tracer.save(run_dir)
        log_event(logger, stage="trace", status="ok", file=trace_path.name)

        log_event(logger, stage="done", status="ok", run_dir=str(run_dir))
        print(f"\n[pipeline] Run completo: {run_dir}")
        print(f"[pipeline] Costo estimado: USD ${total_cost:.3f}")

        # Regenerar dashboard automáticamente
        try:
            import subprocess, sys
            from pathlib import Path as _Path
            _refresh = _Path(__file__).parent.parent.parent / "docs" / "refresh_dashboard.py"
            subprocess.run([sys.executable, str(_refresh)], check=True, capture_output=True)
            print("[pipeline] Dashboard actualizado.")
        except Exception as e:
            print(f"[pipeline] Dashboard no actualizado: {e}")

        # Auto-trigger compilación si hay suficientes videos limpios
        if upload and settings.compilation.auto_trigger:
            try:
                from src.pipelines.compile_videos import should_compile, compile_videos as run_compilation
                target_sec = settings.compilation.target_duration_min * 60
                if should_compile(Path(settings.paths.runs_dir), target_sec):
                    print("[pipeline] Videos suficientes para compilación — iniciando...")
                    run_compilation(
                        runs_dir=Path(settings.paths.runs_dir),
                        target_duration_sec=target_sec,
                        privacy_status=settings.compilation.privacy_status,
                        upload=True,
                    )
                else:
                    print("[pipeline] Compilación: aún no hay suficientes videos.")
            except Exception as e:
                print(f"[pipeline] Error en auto-compilación: {e}")

        return run_dir

    except (EvaluationError, MusicNotFoundError):
        tracer.status = "error"
        tracer.save(run_dir)
        raise  # ya notificados por el inner except

    except Exception as e:
        tb_str = _traceback.format_exc()
        partial_cost = sum(c.get("est_cost_usd", 0.0) for c in costs)
        tracer.status = "error"
        tracer.save(run_dir)
        log_event(logger, stage="pipeline", status="fatal_error", error=str(e))
        print(f"\n[pipeline] ERROR inesperado ({type(e).__name__}): {e}")
        send_run_notification(RunSummary(
            status="error",
            run_dir=run_dir,
            error_type=type(e).__name__,
            error_message=f"{e}\n\n{tb_str}",
            agent_costs=costs,
            total_cost_usd=partial_cost,
            trace=tracer.to_dict(),
        ), settings)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Oldies-Tango daily pipeline")
    parser.add_argument("--image", type=Path, help="Path a imagen (opcional)")
    parser.add_argument("--audio", type=Path, help="Path a audio (opcional)")
    parser.add_argument("--upload", action="store_true", help="Subir video a YouTube al terminar")
    args = parser.parse_args()
    run(image_path=args.image, audio_path=args.audio, upload=args.upload)
