from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.core.brief import Brief
from src.core.settings import PipelineSettings, PromptBundle
from src.core.evaluator import EvaluationError, EvaluationResult
from src.core.evaluation_criteria import MusicPromptEvaluator
from src.core.evaluation_log import EvaluationLogger, create_output_snapshot
from src.media.audio.public_domain import search_and_download

load_dotenv()


class MusicNotFoundError(Exception):
    """No se encontró música en archive.org después de todos los intentos."""
    pass


@dataclass(frozen=True)
class MusicInputs:
    brief: Brief
    settings: PipelineSettings
    prompts: PromptBundle
    feedback: str = ""  # Feedback de evaluación fallida para retry


@dataclass(frozen=True)
class MusicPrompt:
    """Prompt para generar música con Suno (modo ai_generated)."""
    suno_prompt: str
    style_tags: str
    duration_sec: int
    notes: str


@dataclass(frozen=True)
class MusicResult:
    """Resultado unificado del Music Agent (funciona para ambos modos)."""
    source: str           # "public_domain" | "ai_generated"
    audio_path: Path | None  # Path al audio descargado (public_domain)
    title: str
    artist: str
    source_url: str
    notes: str
    suno_prompt: str = ""    # Solo para modo ai_generated
    style_tags: str = ""     # Solo para modo ai_generated


def resolve_music(
    inputs: MusicInputs,
    evaluation_logger: EvaluationLogger | None = None,
) -> MusicResult:
    """
    Resuelve la música para el video según el source_mode configurado.

    - public_domain: busca y descarga de archive.org
    - ai_generated: genera prompt para Suno (requiere paso manual)

    Returns:
        MusicResult con audio_path (public_domain) o suno_prompt (ai_generated)
    """
    mode = inputs.settings.music.source_mode

    if mode == "public_domain":
        return _resolve_public_domain(inputs)
    elif mode == "ai_generated":
        return _resolve_ai_generated(inputs, evaluation_logger)
    else:
        raise ValueError(f"source_mode no válido: {mode}. Usar 'public_domain' o 'ai_generated'")


def _resolve_public_domain(inputs: MusicInputs) -> MusicResult:
    """Busca y descarga un tango de dominio público de archive.org."""
    brief = inputs.brief
    query = brief.music_search_query or f"tango {brief.era}"
    artist_hint = brief.music_search_artist or ""

    print(f"[music_agent] Modo: public_domain")
    print(f"[music_agent] Query: {query}")
    if artist_hint:
        print(f"[music_agent] Artista preferido: {artist_hint}")

    # Artistas fallback conocidos que siempre tienen resultados en archive.org
    FALLBACK_ARTISTS = ["Carlos Gardel", "Francisco Canaro", "Roberto Firpo"]

    # Buscar y descargar desde archive.org
    dest_dir = Path(inputs.settings.paths.runs_dir) / "audio_cache"
    track = search_and_download(query, dest_dir, artist_hint=artist_hint)

    if track:
        return MusicResult(
            source="public_domain",
            audio_path=track.audio_path,
            title=track.title,
            artist=track.artist,
            source_url=track.source_url,
            notes=f"Tango de dominio público descargado de archive.org ({track.identifier})",
        )

    # Fallback: probar con artistas conocidos que siempre tienen resultados
    for fallback_artist in FALLBACK_ARTISTS:
        if fallback_artist.lower() == artist_hint.lower():
            continue  # Ya lo intentamos
        print(f"[music_agent] Intentando fallback con {fallback_artist}...")
        track = search_and_download("tango", dest_dir, artist_hint=fallback_artist)
        if track:
            return MusicResult(
                source="public_domain",
                audio_path=track.audio_path,
                title=track.title,
                artist=track.artist,
                source_url=track.source_url,
                notes=f"Tango fallback de archive.org ({track.identifier}). Query original: {query}",
            )

    # Realmente no se encontró nada — FAIL (no continuar sin música)
    print("[music_agent] ERROR: No se pudo descargar música de archive.org")
    raise MusicNotFoundError(
        f"No se encontró música en archive.org. Query: {query}, Artist: {artist_hint}"
    )


def _resolve_ai_generated(
    inputs: MusicInputs,
    evaluation_logger: EvaluationLogger | None = None,
) -> MusicResult:
    """Genera un prompt para Suno AI (modo ai_generated)."""
    music_prompt, eval_result = create_music_prompt(
        inputs,
        evaluation_logger=evaluation_logger,
    )
    return MusicResult(
        source="ai_generated",
        audio_path=None,
        title="",
        artist="",
        source_url="",
        notes=music_prompt.notes,
        suno_prompt=music_prompt.suno_prompt,
        style_tags=music_prompt.style_tags,
    )


# --- Código original de ai_generated (mantenido para compatibilidad) ---


def create_music_prompt(
    inputs: MusicInputs,
    max_attempts: int = 2,
    threshold: float = 0.90,
    evaluation_logger: EvaluationLogger | None = None
) -> tuple[MusicPrompt, EvaluationResult]:
    """
    Genera un prompt de audio basado en el brief.
    Evalúa el output y reintenta si no pasa el umbral.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("[music_agent] ANTHROPIC_API_KEY no configurada, usando fallback")
        music_prompt = _create_fallback_prompt(inputs)
        evaluator = MusicPromptEvaluator(brief=inputs.brief, threshold=threshold)
        result = evaluator.evaluate(music_prompt)
        if evaluation_logger:
            evaluation_logger.log_evaluation(
                result, "music_agent", 1,
                create_output_snapshot(music_prompt)
            )
        return music_prompt, result

    evaluator = MusicPromptEvaluator(brief=inputs.brief, threshold=threshold)
    current_inputs = inputs
    last_result: EvaluationResult | None = None

    for attempt in range(1, max_attempts + 1):
        print(f"[music_agent] Intento {attempt}/{max_attempts}")

        music_prompt = _create_prompt_with_claude(current_inputs, api_key)
        result = evaluator.evaluate(music_prompt)

        if evaluation_logger:
            evaluation_logger.log_evaluation(
                result, "music_agent", attempt,
                create_output_snapshot(music_prompt)
            )

        if result.meets_threshold():
            print(f"[music_agent] MusicPrompt aprobado ({result.percentage:.1%})")
            return music_prompt, result

        last_result = result
        print(f"[music_agent] MusicPrompt rechazado ({result.percentage:.1%})")

        if attempt < max_attempts:
            current_inputs = MusicInputs(
                brief=inputs.brief,
                settings=inputs.settings,
                prompts=inputs.prompts,
                feedback=result.feedback
            )

    raise EvaluationError(
        f"MusicPrompt no pasó evaluación después de {max_attempts} intentos. "
        f"Último score: {last_result.percentage:.1%} (umbral: {threshold:.0%}). "
        f"Revisar criterios fallidos: {[c.name for c in last_result.failed_criteria]}"
    )


def _create_prompt_with_claude(inputs: MusicInputs, api_key: str) -> MusicPrompt:
    """Genera el prompt de audio usando Claude con structured output (tool use)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = inputs.prompts.music

    music_tool = {
        "name": "generate_music_prompt",
        "description": "Genera un prompt de musica para Suno AI basado en un brief creativo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "suno_prompt": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "Prompt para Suno en ingles, MAXIMO 500 caracteres, solo musica"
                },
                "style_tags": {
                    "type": "string",
                    "description": "Tags separados por comas en ingles"
                },
                "duration_sec": {
                    "type": "integer",
                    "description": "Duracion sugerida en segundos"
                },
                "notes": {
                    "type": "string",
                    "description": "Notas en espanol para referencia"
                }
            },
            "required": ["suno_prompt", "style_tags", "duration_sec", "notes"]
        }
    }

    brief = inputs.brief
    user_message = (
        f"Genera un prompt de audio para Suno basado en este brief:\n\n"
        f"- Titulo: {brief.title}\n"
        f"- Mood: {brief.mood}\n"
        f"- Era: {brief.era}\n"
        f"- Ambience: {brief.ambience}\n"
        f"- Audio notes: {brief.audio_notes}\n"
        f"- Visual notes: {brief.visual_notes}\n"
        f"- Duracion: {brief.duration_sec} segundos"
    )

    if inputs.feedback:
        user_message += (
            f"\n\nIMPORTANTE: Tu intento anterior fue rechazado. "
            f"Corrige estos problemas:\n{inputs.feedback}"
        )

    print("[music_agent] Llamando a Claude (structured output)...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        tools=[music_tool],
        tool_choice={"type": "tool", "name": "generate_music_prompt"},
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    tool_block = next(b for b in message.content if b.type == "tool_use")
    data = tool_block.input
    print("[music_agent] Respuesta recibida (structured output)")

    suno_prompt = data.get("suno_prompt", "")

    prompt_len = len(suno_prompt)
    if prompt_len > 500:
        print(f"[music_agent] WARNING: Prompt tiene {prompt_len} caracteres (maximo Suno: 500)")
        print(f"[music_agent] Truncando prompt...")
        suno_prompt = suno_prompt[:497] + "..."
    else:
        print(f"[music_agent] Prompt OK: {prompt_len}/500 caracteres")

    return MusicPrompt(
        suno_prompt=suno_prompt,
        style_tags=data.get("style_tags", ""),
        duration_sec=data.get("duration_sec", inputs.brief.duration_sec),
        notes=data.get("notes", "Generado por Claude (structured output)"),
    )


def _create_fallback_prompt(inputs: MusicInputs) -> MusicPrompt:
    """Fallback basado en el brief sin usar IA."""
    brief = inputs.brief
    return MusicPrompt(
        suno_prompt=(
            f"Instrumental tango from Argentina. "
            f"{brief.mood}. Vintage lo-fi recording quality with vinyl crackle. "
            f"Bandoneón and violin as main instruments. "
            f"{brief.era}. Duration {brief.duration_sec} seconds."
        ),
        style_tags="tango, instrumental, vintage, lo-fi, bandoneón",
        duration_sec=brief.duration_sec,
        notes=f"Fallback basado en brief: {brief.title}",
    )
