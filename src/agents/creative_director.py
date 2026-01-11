from __future__ import annotations

from dataclasses import dataclass

from src.core.brief import Brief
from src.core.settings import PipelineSettings, PromptBundle


@dataclass(frozen=True)
class CreativeInputs:
    settings: PipelineSettings
    prompts: PromptBundle


def create_brief(inputs: CreativeInputs) -> Brief:
    """
    Crea un brief inicial (placeholder) usando settings + prompts.
    En el futuro, este paso puede usar un modelo de IA.
    """
    return Brief(
        title="Tango Sonando en un Taller de Autos y está lloviendo, 1956 ASMR",
        mood="nostalgia, Argentina durante los 50-60, calidez en un día lluvioso",
        era="Argentina en los 50-60",
        ambience="lluvioso sin truenos, luces cálidas en un día nublado, escena estática",
        duration_sec=inputs.settings.project.default_duration_sec,
        audio_notes=(
            "Lluvia leve de fondo, tango vintage, sensación de escuchar desde afuera; "
            "sonido relajante para acompañar actividades; duración 180 segundos."
        ),
        visual_notes="Imagen estática, estética vintage, atmósfera lluviosa y cálida.",
        notes="Brief inicial para el MVP basado en la plantilla definida.",
    )
