"""
Criterios de evaluación específicos para cada tipo de output.

- BriefEvaluator: evalúa outputs del Creative Director
- MusicPromptEvaluator: evalúa outputs del Music Agent
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from src.core.brief import Brief
from src.core.evaluator import (
    Criterion,
    CriterionResult,
    Evaluator,
    detect_language_english,
)


class BriefEvaluator(Evaluator):
    """Evaluador para outputs del Creative Director (Brief)."""

    def get_criteria(self) -> list[Criterion]:
        return [
            # Criterios objetivos
            Criterion("title_not_empty", "objective", 1.0, "El título tiene más de 10 caracteres"),
            Criterion("title_has_year", "objective", 1.0, "El título contiene un año (19XX)"),
            Criterion("mood_not_empty", "objective", 1.0, "El mood tiene más de 5 caracteres"),
            Criterion("era_valid", "objective", 1.0, "La era menciona Argentina/Buenos Aires + década"),
            Criterion("dalle_prompt_length", "objective", 2.0, "El dalle_prompt tiene más de 500 caracteres"),
            Criterion("dalle_prompt_english", "objective", 1.0, "El dalle_prompt está en inglés"),
            Criterion("audio_fx_valid", "objective", 1.0, "Los audio_fx son válidos (rain, vinyl, lofi)"),
            Criterion("iconic_figure_present", "objective", 1.0, "Hay una figura icónica mencionada"),
            # Criterios subjetivos
            Criterion("image_text_intimate", "subjective", 2.0, "El concepto es emotivo e íntimo, no genérico"),
            Criterion("concept_original", "subjective", 2.0, "El concepto es creativo y único"),
        ]

    def evaluate_criterion_objective(self, criterion: Criterion, output: Any) -> CriterionResult:
        """Evalúa un criterio objetivo para un Brief."""
        brief: Brief = output

        if criterion.name == "title_not_empty":
            passed = len(brief.title) > 10
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else f"Título muy corto: {len(brief.title)} chars"
            )

        elif criterion.name == "title_has_year":
            has_year = bool(re.search(r'19\d{2}', brief.title))
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=has_year,
                score=1.0 if has_year else 0.0,
                reason=None if has_year else "Título no contiene año (19XX)"
            )

        elif criterion.name == "mood_not_empty":
            passed = len(brief.mood) > 5
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else f"Mood muy corto: {len(brief.mood)} chars"
            )

        elif criterion.name == "era_valid":
            era_lower = brief.era.lower()
            # Locaciones argentinas comunes
            argentina_locations = [
                "argentina", "buenos aires", "córdoba", "cordoba", "rosario",
                "mendoza", "la plata", "mar del plata", "tucumán", "tucuman",
                "salta", "santa fe", "san juan", "entre ríos", "entre rios",
                "patagonia", "bariloche", "ushuaia", "porte", "porteñ"
            ]
            has_location = any(loc in era_lower for loc in argentina_locations)
            # Acepta: 1950s, 1950, años 50, 50s, 50-60, década del 50, etc.
            has_decade = bool(re.search(r'19[3-6]\d|[3-6]0s|[3-6]0-[3-6]0|década.*[3-6]0|años?\s*[3-6]0', era_lower))
            passed = has_location and has_decade
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.5 if (has_location or has_decade) else 0.0,
                reason=None if passed else f"Era incompleta: location={has_location}, decade={has_decade}"
            )

        elif criterion.name == "dalle_prompt_length":
            length = len(brief.dalle_prompt)
            passed = length > 500
            # Score parcial si está cerca
            if passed:
                score = 1.0
            elif length > 400:
                score = 0.7
            elif length > 300:
                score = 0.5
            else:
                score = 0.0
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=score,
                reason=None if passed else f"dalle_prompt corto: {length} chars (mínimo 500)"
            )

        elif criterion.name == "dalle_prompt_english":
            is_english = detect_language_english(brief.dalle_prompt)
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=is_english,
                score=1.0 if is_english else 0.0,
                reason=None if is_english else "dalle_prompt no está en inglés"
            )

        elif criterion.name == "audio_fx_valid":
            valid_fx = {"rain", "vinyl", "lofi"}
            all_valid = all(fx in valid_fx for fx in brief.audio_fx)
            has_fx = len(brief.audio_fx) > 0
            passed = all_valid and has_fx
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.5 if all_valid else 0.0,
                reason=None if passed else f"audio_fx inválidos o vacíos: {brief.audio_fx}"
            )

        elif criterion.name == "iconic_figure_present":
            passed = len(brief.iconic_figure) > 5
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else "No hay figura icónica"
            )

        return CriterionResult(
            name=criterion.name,
            criterion_type="objective",
            weight=criterion.weight,
            passed=False,
            score=0.0,
            reason=f"Criterio no implementado: {criterion.name}"
        )

    def get_subjective_prompt(self, criterion: Criterion, output: Any) -> str:
        """Genera el prompt para evaluación subjetiva del Brief."""
        brief: Brief = output
        brief_summary = (
            f"Título: {brief.title}\n"
            f"Mood: {brief.mood}\n"
            f"Era: {brief.era}\n"
            f"Ambiente: {brief.ambience}\n"
            f"Figura icónica: {brief.iconic_figure}\n"
            f"Texto de imagen: {brief.image_text}"
        )

        if criterion.name == "image_text_intimate":
            return (
                f"Evalúa si este concepto de video es emotivo e íntimo (no genérico).\n\n"
                f"{brief_summary}\n\n"
                f"Responde con un número del 0 al 10 seguido de una breve explicación.\n"
                f"10 = muy emotivo e íntimo, transporta al espectador a esa época\n"
                f"0 = genérico, sin alma, podría ser de cualquier video de stock"
            )

        elif criterion.name == "concept_original":
            return (
                f"Evalúa si este concepto de video es creativo y único.\n\n"
                f"{brief_summary}\n\n"
                f"Responde con un número del 0 al 10 seguido de una breve explicación.\n"
                f"10 = muy original, escenario único e inesperado\n"
                f"0 = cliché, escenario predecible (ej: 'café con lluvia' genérico)"
            )

        return f"Evalúa: {criterion.description}\n\n{brief_summary}"


class MusicPromptEvaluator(Evaluator):
    """Evaluador para outputs del Music Agent (MusicPrompt)."""

    def __init__(self, brief: Brief | None = None, **kwargs):
        super().__init__(**kwargs)
        self.brief = brief  # Para verificar coherencia

    def get_criteria(self) -> list[Criterion]:
        return [
            # Criterios objetivos
            Criterion("suno_prompt_not_empty", "objective", 1.0, "El prompt tiene más de 20 caracteres"),
            Criterion("suno_prompt_max_length", "objective", 2.0, "El prompt tiene máximo 500 caracteres"),
            Criterion("suno_prompt_no_fx", "objective", 2.0, "El prompt NO contiene efectos de ambiente"),
            Criterion("suno_prompt_english", "objective", 1.0, "El prompt está en inglés"),
            Criterion("style_tags_present", "objective", 1.0, "Hay style_tags con más de 5 caracteres"),
            # Criterios subjetivos
            Criterion("music_coherent", "subjective", 2.0, "El prompt es coherente con el brief"),
        ]

    def evaluate_criterion_objective(self, criterion: Criterion, output: Any) -> CriterionResult:
        """Evalúa un criterio objetivo para MusicPrompt."""
        # output es un dict o MusicPrompt
        if hasattr(output, 'suno_prompt'):
            suno_prompt = output.suno_prompt
            style_tags = output.style_tags
        else:
            suno_prompt = output.get("suno_prompt", "")
            style_tags = output.get("style_tags", "")

        if criterion.name == "suno_prompt_not_empty":
            passed = len(suno_prompt) > 20
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else f"Prompt muy corto: {len(suno_prompt)} chars"
            )

        elif criterion.name == "suno_prompt_max_length":
            length = len(suno_prompt)
            passed = length <= 500
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else f"Prompt excede límite: {length}/500 chars"
            )

        elif criterion.name == "suno_prompt_no_fx":
            # Efectos de ambiente que NO deben estar en el prompt de música
            forbidden_fx = ["rain", "vinyl", "crackle", "lo-fi", "lofi", "room", "ambient", "café", "coffee shop"]
            prompt_lower = suno_prompt.lower()
            found_fx = [fx for fx in forbidden_fx if fx in prompt_lower]
            passed = len(found_fx) == 0
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else f"Prompt contiene efectos prohibidos: {found_fx}"
            )

        elif criterion.name == "suno_prompt_english":
            is_english = detect_language_english(suno_prompt)
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=is_english,
                score=1.0 if is_english else 0.0,
                reason=None if is_english else "Prompt no está en inglés"
            )

        elif criterion.name == "style_tags_present":
            passed = len(style_tags) > 5
            return CriterionResult(
                name=criterion.name,
                criterion_type="objective",
                weight=criterion.weight,
                passed=passed,
                score=1.0 if passed else 0.0,
                reason=None if passed else f"Style tags muy cortos: {len(style_tags)} chars"
            )

        return CriterionResult(
            name=criterion.name,
            criterion_type="objective",
            weight=criterion.weight,
            passed=False,
            score=0.0,
            reason=f"Criterio no implementado: {criterion.name}"
        )

    def get_subjective_prompt(self, criterion: Criterion, output: Any) -> str:
        """Genera el prompt para evaluación subjetiva del MusicPrompt."""
        if hasattr(output, 'suno_prompt'):
            suno_prompt = output.suno_prompt
            style_tags = output.style_tags
        else:
            suno_prompt = output.get("suno_prompt", "")
            style_tags = output.get("style_tags", "")

        if criterion.name == "music_coherent":
            brief_context = ""
            if self.brief:
                brief_context = (
                    f"\nContexto del video:\n"
                    f"- Título: {self.brief.title}\n"
                    f"- Mood: {self.brief.mood}\n"
                    f"- Era: {self.brief.era}\n"
                    f"- Ambiente: {self.brief.ambience}\n"
                )

            return (
                f"Evalúa si este prompt de música es coherente con el video que acompañará.\n\n"
                f"Prompt para Suno: {suno_prompt}\n"
                f"Style tags: {style_tags}"
                f"{brief_context}\n\n"
                f"Responde con un número del 0 al 10 seguido de una breve explicación.\n"
                f"10 = perfectamente coherente, la música complementará el video\n"
                f"0 = incoherente, la música no tiene relación con el concepto"
            )

        return f"Evalúa: {criterion.description}\n\nPrompt: {suno_prompt}"
