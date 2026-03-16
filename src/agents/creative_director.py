from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv

from src.core.brief import Brief
from src.core.settings import PipelineSettings, PromptBundle
from src.core.evaluator import EvaluationError, EvaluationResult
from src.core.evaluation_criteria import BriefEvaluator
from src.core.evaluation_log import EvaluationLogger, create_output_snapshot

load_dotenv()


@dataclass(frozen=True)
class CreativeInputs:
    settings: PipelineSettings
    prompts: PromptBundle
    feedback: str = ""  # Feedback de evaluación fallida para retry


def create_brief(
    inputs: CreativeInputs,
    max_attempts: int = 2,
    threshold: float = 0.90,
    evaluation_logger: EvaluationLogger | None = None
) -> tuple[Brief, EvaluationResult]:
    """
    Crea un brief usando Claude como director creativo.
    Evalúa el output y reintenta si no pasa el umbral.

    Args:
        inputs: Configuración y prompts
        max_attempts: Máximo de intentos antes de lanzar error
        threshold: Umbral de aprobación (0.90 = 90%)
        evaluation_logger: Logger para registrar evaluaciones

    Returns:
        Tupla (Brief, EvaluationResult)

    Raises:
        EvaluationError: Si falla después de max_attempts
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("[creative_director] ANTHROPIC_API_KEY no configurada, usando fallback")
        brief = _create_fallback_brief(inputs)
        # Evaluar incluso el fallback
        evaluator = BriefEvaluator(threshold=threshold)
        result = evaluator.evaluate(brief)
        if evaluation_logger:
            evaluation_logger.log_evaluation(
                result, "creative_director", 1,
                create_output_snapshot(brief)
            )
        return brief, result

    evaluator = BriefEvaluator(threshold=threshold)
    current_inputs = inputs
    last_result: EvaluationResult | None = None

    for attempt in range(1, max_attempts + 1):
        print(f"[creative_director] Intento {attempt}/{max_attempts}")

        brief = _create_brief_with_claude(current_inputs, api_key)
        result = evaluator.evaluate(brief)

        # Loguear siempre
        if evaluation_logger:
            evaluation_logger.log_evaluation(
                result, "creative_director", attempt,
                create_output_snapshot(brief)
            )

        if result.meets_threshold():
            print(f"[creative_director] Brief aprobado ({result.percentage:.1%})")
            return brief, result

        # Preparar feedback para siguiente intento
        last_result = result
        print(f"[creative_director] Brief rechazado ({result.percentage:.1%})")

        if attempt < max_attempts:
            # Agregar feedback al próximo intento
            current_inputs = CreativeInputs(
                settings=inputs.settings,
                prompts=inputs.prompts,
                feedback=result.feedback
            )

    # Falló después de todos los intentos
    raise EvaluationError(
        f"Brief no pasó evaluación después de {max_attempts} intentos. "
        f"Último score: {last_result.percentage:.1%} (umbral: {threshold:.0%}). "
        f"Revisar criterios fallidos: {[c.name for c in last_result.failed_criteria]}"
    )


def _create_brief_with_claude(inputs: CreativeInputs, api_key: str) -> Brief:
    """Genera un brief usando la API de Claude con structured output (tool use)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = inputs.prompts.creative_director

    # Tool schema: define la estructura exacta del brief
    brief_tool = {
        "name": "generate_brief",
        "description": "Genera un brief creativo para un video de tango vintage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titulo atractivo para YouTube"},
                "mood": {"type": "string", "description": "Atmosfera emocional"},
                "era": {"type": "string", "description": "Decada y lugar especifico"},
                "ambience": {"type": "string", "description": "Descripcion del ambiente"},
                "audio_notes": {"type": "string", "description": "Instrucciones para el audio"},
                "visual_notes": {"type": "string", "description": "Instrucciones para la imagen"},
                "audio_fx": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["rain", "vinyl", "lofi"]},
                    "description": "Efectos de audio a aplicar"
                },
                "iconic_figure": {"type": "string", "description": "Personaje real de la epoca"},
                "image_text": {"type": "string", "description": "Texto para mostrar en la imagen"},
                "animatable_elements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Elementos que pueden animarse en loop"
                },
                "dalle_prompt": {"type": "string", "description": "Prompt en ingles para DALL-E 3"},
                "music_search_query": {"type": "string", "description": "Query para buscar en archive.org (ej: 'tango gardel 1930s')"},
                "music_search_artist": {"type": "string", "description": "Artista preferido de dominio publico (ej: 'Carlos Gardel')"},
                "music_search_style": {"type": "string", "description": "Estilo/mood musical para filtrar (ej: 'melancolico, vals')"}
            },
            "required": ["title", "mood", "era", "ambience", "audio_notes", "visual_notes",
                         "audio_fx", "iconic_figure", "image_text", "animatable_elements", "dalle_prompt",
                         "music_search_query", "music_search_artist", "music_search_style"]
        }
    }

    # Mensaje base
    user_message = (
        "Genera un concepto nuevo y unico para el video de hoy. "
        "Busca algo diferente a los ejemplos, pero manteniendo el estilo del canal."
    )

    # Agregar feedback si viene de un retry
    if inputs.feedback:
        user_message += (
            f"\n\nIMPORTANTE: Tu intento anterior fue rechazado. "
            f"Corrige estos problemas:\n{inputs.feedback}"
        )

    print("[creative_director] Llamando a Claude (structured output)...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=system_prompt,
        tools=[brief_tool],
        tool_choice={"type": "tool", "name": "generate_brief"},
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    # Extraer datos directamente del tool_use block (JSON garantizado)
    tool_block = next(b for b in message.content if b.type == "tool_use")
    data = tool_block.input
    print(f"[creative_director] Respuesta recibida (structured output)")

    return Brief(
        title=data.get("title", "Sin titulo"),
        mood=data.get("mood", "nostalgico"),
        era=data.get("era", "Argentina 1950s"),
        ambience=data.get("ambience", "ambiente vintage"),
        duration_sec=inputs.settings.project.default_duration_sec,
        audio_notes=data.get("audio_notes", "tango vintage"),
        visual_notes=data.get("visual_notes", "estetica vintage"),
        audio_fx=data.get("audio_fx", ["rain", "lofi"]),
        iconic_figure=data.get("iconic_figure", ""),
        image_text=data.get("image_text", ""),
        animatable_elements=data.get("animatable_elements", []),
        dalle_prompt=data.get("dalle_prompt", ""),
        music_search_query=data.get("music_search_query", ""),
        music_search_artist=data.get("music_search_artist", ""),
        music_search_style=data.get("music_search_style", ""),
        notes="Brief generado por Claude (structured output)",
    )


def _create_fallback_brief(inputs: CreativeInputs) -> Brief:
    """Brief de fallback cuando no hay API key."""
    return Brief(
        title="Tango Sonando en un Taller de Autos y esta lloviendo, 1956 ASMR",
        mood="nostalgia, Argentina durante los 50-60, calidez en un dia lluvioso",
        era="Buenos Aires, Argentina 1950s",
        audio_fx=["rain", "lofi"],
        ambience="lluvioso sin truenos, luces calidas en un dia nublado, escena estatica",
        duration_sec=inputs.settings.project.default_duration_sec,
        audio_notes=(
            "Lluvia leve de fondo, tango vintage, sensacion de escuchar desde afuera; "
            "sonido relajante para acompanar actividades; duracion 180 segundos."
        ),
        visual_notes="Imagen estatica, estetica vintage, atmosfera lluviosa y calida.",
        iconic_figure="Anibal Troilo - el bandoneonista mas famoso de la epoca",
        image_text="Buenos Aires, 1956",
        animatable_elements=["lluvia en la ventana", "humo de cigarrillo", "gotas cayendo"],
        dalle_prompt=(
            "Image for Oldies Tango YouTube channel. POV ambience / 'oldies playing' style video "
            "designed to transport viewers to Argentina in the 1940s-1960s golden era while they study, work, or relax. "
            "The image must awaken deep NOSTALGIA and EMOTION in Argentine viewers. "
            "STYLE: Vintage illustration aesthetic, like a nostalgic book illustration or Studio Ghibli with Argentine flavor. "
            "NOT photorealistic. Warm color palette with golden yellows, soft blues, amber tones. Soft painterly texture. "
            "SCENE: Interior of a 1956 Buenos Aires auto repair shop on a rainy afternoon. A moment of rest and tango. "
            "An older mechanic in oil-stained overalls sits on a wooden crate, mate in hand, listening to tango on the radio "
            "while rain streams down the large garage windows. His expression is peaceful - this is his daily ritual. "
            "ICONIC FIGURE: Tango of Aníbal Troilo plays from the wooden radio - a small photo of 'Pichuco' is tucked into the mirror. "
            "AUTHENTIC ARGENTINE DETAILS 1956: Siam tools calendar on wall, YPF oil cans, Ford pickup truck from the era, "
            "wooden radio, mate gourd with bombilla, soda siphon on workbench, La Razón newspaper, Geniol aspirin sign. "
            "LIGHTING: Grey rainy afternoon light from windows mixed with warm yellow from hanging work lamps. Cozy despite the rain. "
            "TEXT: In vintage hand-painted typography: 'Tarde de lluvia en el taller - 1956'. Intimate, emotional title. "
            "16:9 composition. NO modern elements. NO photorealistic. NO empty scenes. The mechanic's peaceful moment is the soul."
        ),
        notes="Brief de fallback (ANTHROPIC_API_KEY no configurada)",
    )
