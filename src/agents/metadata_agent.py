from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.core.brief import Brief
from src.core.settings import PipelineSettings, PromptBundle

load_dotenv()


@dataclass(frozen=True)
class MusicInfo:
    """Info de la canción usada — subconjunto de MusicResult para evitar dependencia circular."""
    title: str
    artist: str
    source: str       # "public_domain" | "ai_generated"
    source_url: str


@dataclass(frozen=True)
class MetadataInputs:
    brief: Brief
    music_info: MusicInfo
    settings: PipelineSettings
    prompts: PromptBundle


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    description: str
    tags: list[str]
    category: str    # "Music" — YouTube category_id "10" al publicar
    notes: str


def generate_metadata(inputs: MetadataInputs) -> VideoMetadata:
    """
    Genera metadata optimizada para YouTube basándose en el brief y la canción usada.
    Usa Claude con structured output (tool use).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("[metadata_agent] ANTHROPIC_API_KEY no configurada, usando fallback")
        return _create_fallback_metadata(inputs)

    return _generate_with_claude(inputs, api_key)


def _generate_with_claude(inputs: MetadataInputs, api_key: str) -> VideoMetadata:
    """Genera metadata usando Claude con structured output (tool use)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    metadata_tool = {
        "name": "generate_metadata",
        "description": "Genera metadata SEO optimizada para YouTube de un video de tango vintage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "Título optimizado para YouTube, máximo 100 chars (ideal 60-70). Hook emocional + keyword principal."
                },
                "description": {
                    "type": "string",
                    "description": "Descripción completa para YouTube. Primeros 150 chars críticos para SEO. Incluir escena, canción, efectos, CTA y hashtags al final."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tags para YouTube. Máximo 500 chars totales (suma de todos). Los más importantes primero. Mezclar español e inglés."
                },
                "category": {
                    "type": "string",
                    "enum": ["Music", "Entertainment"],
                    "description": "Categoría YouTube. Usar 'Music' para videos de tango."
                },
                "notes": {
                    "type": "string",
                    "description": "Notas sobre la estrategia SEO aplicada (en español, para referencia interna)."
                }
            },
            "required": ["title", "description", "tags", "category", "notes"]
        }
    }

    brief = inputs.brief
    music = inputs.music_info

    audio_fx_str = ", ".join(brief.audio_fx) if brief.audio_fx else "ninguno"

    user_message = (
        f"Genera metadata SEO optimizada para YouTube de este video de tango vintage.\n\n"
        f"=== BRIEF DEL VIDEO ===\n"
        f"Título creativo: {brief.title}\n"
        f"Mood/atmósfera: {brief.mood}\n"
        f"Era y lugar: {brief.era}\n"
        f"Ambiente: {brief.ambience}\n"
        f"Figura icónica: {brief.iconic_figure}\n"
        f"Efectos de audio: {audio_fx_str}\n\n"
        f"=== MÚSICA USADA ===\n"
        f"Canción: {music.title}\n"
        f"Artista: {music.artist}\n"
        f"Fuente: {music.source}\n"
    )

    print("[metadata_agent] Llamando a Claude (structured output)...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=inputs.prompts.metadata,
        tools=[metadata_tool],
        tool_choice={"type": "tool", "name": "generate_metadata"},
        messages=[{"role": "user", "content": user_message}]
    )

    tool_block = next(b for b in message.content if b.type == "tool_use")
    data = tool_block.input
    print("[metadata_agent] Respuesta recibida (structured output)")

    tags = data.get("tags", [])
    tags_total_chars = sum(len(t) for t in tags)
    if tags_total_chars > 500:
        print(f"[metadata_agent] WARNING: Tags tienen {tags_total_chars} chars (máximo YouTube: 500)")
        trimmed = []
        count = 0
        for tag in tags:
            if count + len(tag) + 1 <= 500:
                trimmed.append(tag)
                count += len(tag) + 1
            else:
                break
        tags = trimmed
        print(f"[metadata_agent] Tags recortados a {len(tags)} ({sum(len(t) for t in tags)} chars)")

    title = data.get("title", brief.title)
    if len(title) > 100:
        print(f"[metadata_agent] WARNING: Título tiene {len(title)} chars (máximo: 100). Truncando.")
        title = title[:97] + "..."

    description = data.get("description", "")
    description = _append_footer(description, inputs.settings)

    return VideoMetadata(
        title=title,
        description=description,
        tags=tags,
        category=data.get("category", "Music"),
        notes=data.get("notes", "Generado por Claude (structured output)"),
    )


def _append_footer(description: str, settings) -> str:
    """Agrega links del canal al final de la descripción si están configurados."""
    cafecito = getattr(settings.channel, "cafecito_url", "")
    if not cafecito:
        return description
    footer = f"\n\n☕ Si disfrutás el canal, invitanos un café: {cafecito}"
    return description + footer


def _create_fallback_metadata(inputs: MetadataInputs) -> VideoMetadata:
    """Fallback basado en el brief sin usar IA."""
    brief = inputs.brief
    music = inputs.music_info

    title = brief.title if len(brief.title) <= 100 else brief.title[:97] + "..."

    fx_lines = []
    for fx in brief.audio_fx:
        if fx == "rain":
            fx_lines.append("lluvia suave de fondo")
        elif fx == "vinyl":
            fx_lines.append("crujido de disco de vinilo")
        elif fx == "lofi":
            fx_lines.append("calidad vintage lofi")
        else:
            fx_lines.append(fx)
    fx_str = ", ".join(fx_lines) if fx_lines else "ambiente vintage"

    music_line = f"🎼 {music.title} - {music.artist}" if music.title else "🎼 Tango argentino de dominio público"

    description = (
        f"Tango argentino vintage — {brief.mood}. {brief.era}.\n\n"
        f"{brief.ambience}\n\n"
        f"{music_line}\n"
        f"📍 {brief.era}\n"
        f"🎶 Efectos de ambiente: {fx_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"¿Qué escena argentina querés que hagamos? Dejá tu sugerencia en los comentarios 💬\n\n"
        f"🔔 Suscribite para más tangos vintage argentinos\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"#tango #tangoargentino #musicaargentina #argentina #tangoclasico "
        f"#buenosaires #nostalgia #ASMR #lofi #vintagemusic"
    )

    tags = [
        "tango", "tango argentino", "tangos", "tango clasico",
        "musica argentina", "argentina", "buenos aires",
        "nostalgia argentina", "tango nostalgico",
        "musica de fondo", "tango para estudiar",
        "vintage tango", "argentine tango", "tango music",
        "ASMR", "lofi tango",
    ]
    if music.artist and music.artist not in tags:
        tags.insert(6, music.artist)

    description = _append_footer(description, inputs.settings)

    return VideoMetadata(
        title=title,
        description=description,
        tags=tags,
        category="Music",
        notes="Fallback generado sin API (basado en brief)",
    )
