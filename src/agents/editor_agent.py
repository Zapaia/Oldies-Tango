from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.core.brief import Brief

load_dotenv()


@dataclass(frozen=True)
class EditorDecision:
    """Decisiones de edicion para el renderer."""
    fade_duration: float      # Segundos de fade in/out
    title_text: str           # Texto para mostrar en pantalla (futuro)
    notes: str = ""           # Razonamiento del agente (debug)


def decide_edit(brief: Brief) -> EditorDecision:
    """
    Editor Agent: lee el brief y decide los parametros de edicion del video.

    Usa Claude si hay API key, sino fallback basado en el mood.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("[editor_agent] ANTHROPIC_API_KEY no configurada, usando fallback")
        return _fallback_decision(brief)

    return _decide_with_claude(brief, api_key)


def _decide_with_claude(brief: Brief, api_key: str) -> EditorDecision:
    """Decide parametros de edicion usando Claude (structured output via tool use)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    editor_tool = {
        "name": "decide_edit",
        "description": "Decide los parametros de edicion para el video de tango.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fade_duration": {
                    "type": "number",
                    "description": (
                        "Duracion del fade in/out en segundos. "
                        "Moods melancolicos/lentos: 3-4s. "
                        "Alegres/energicos: 1-2s. "
                        "Neutros/romanticos: 2-3s."
                    )
                },
                "title_text": {
                    "type": "string",
                    "description": (
                        "Texto corto para mostrar en pantalla sobre la imagen. "
                        "Usar el titulo del brief o una variacion poetica. "
                        "Max 50 caracteres."
                    )
                },
                "notes": {
                    "type": "string",
                    "description": "Breve razonamiento de las decisiones tomadas."
                }
            },
            "required": ["fade_duration", "title_text", "notes"]
        }
    }

    system_prompt = (
        "Eres el Editor de un canal de tango vintage en YouTube. "
        "Tu trabajo es decidir los parametros de edicion del video basandote en el brief creativo. "
        "El video es una imagen estatica con musica de tango y efectos de ambiente (lluvia, vinyl). "
        "Tu unica herramienta de edicion por ahora es el fade in/out. "
        "Toma decisiones coherentes con el mood y la atmosfera del brief."
    )

    user_message = (
        f"Brief del video:\n"
        f"- Titulo: {brief.title}\n"
        f"- Mood: {brief.mood}\n"
        f"- Era: {brief.era}\n"
        f"- Ambiente: {brief.ambience}\n"
        f"- Efectos de audio: {', '.join(brief.audio_fx)}\n\n"
        f"Decide los parametros de edicion para este video."
    )

    print("[editor_agent] Llamando a Claude para decisiones de edicion...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=system_prompt,
        tools=[editor_tool],
        tool_choice={"type": "tool", "name": "decide_edit"},
        messages=[{"role": "user", "content": user_message}]
    )

    tool_block = next(b for b in message.content if b.type == "tool_use")
    data = tool_block.input

    decision = EditorDecision(
        fade_duration=float(data.get("fade_duration", 2.0)),
        title_text=str(data.get("title_text", brief.title)),
        notes=str(data.get("notes", "")),
    )

    print(f"[editor_agent] Fade: {decision.fade_duration}s | Titulo: '{decision.title_text}'")
    print(f"[editor_agent] Razonamiento: {decision.notes}")
    return decision


def _fallback_decision(brief: Brief) -> EditorDecision:
    """Fallback simple basado en palabras clave del mood."""
    mood_lower = brief.mood.lower()

    if any(w in mood_lower for w in ["melanc", "triste", "lento", "nostalgico", "nostalgia"]):
        fade = 3.5
    elif any(w in mood_lower for w in ["alegre", "festivo", "rapido", "energico"]):
        fade = 1.5
    else:
        fade = 2.0

    return EditorDecision(
        fade_duration=fade,
        title_text=brief.title[:50],
        notes=f"Fallback basado en mood: '{brief.mood}' → fade={fade}s",
    )
