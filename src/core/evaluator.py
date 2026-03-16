"""
Sistema base de evaluación para outputs de agentes.

Evalúa outputs en dos capas:
- Objetiva: código Python puro (formato, longitud, campos)
- Subjetiva: Claude Haiku evalúa calidad/coherencia
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class EvaluationError(Exception):
    """Error lanzado cuando un output falla la evaluación después de max_attempts."""
    pass


@dataclass
class CriterionResult:
    """Resultado de evaluar un criterio individual."""
    name: str
    criterion_type: str  # "objective" o "subjective"
    weight: float
    passed: bool
    score: float  # 0.0 a 1.0
    reason: str | None = None


@dataclass
class EvaluationResult:
    """Resultado completo de una evaluación."""
    total_score: float
    max_score: float
    percentage: float
    threshold: float
    passed: bool
    criteria: list[CriterionResult] = field(default_factory=list)
    failed_criteria: list[CriterionResult] = field(default_factory=list)
    feedback: str = ""

    def meets_threshold(self) -> bool:
        return self.passed


@dataclass
class Criterion:
    """Define un criterio de evaluación."""
    name: str
    criterion_type: str  # "objective" o "subjective"
    weight: float
    description: str


class Evaluator(ABC):
    """Clase base para evaluadores de outputs de agentes."""

    def __init__(self, threshold: float = 0.90, subjective_model: str = "claude-haiku-4-5-20251001"):
        self.threshold = threshold
        self.subjective_model = subjective_model
        self._criteria: list[Criterion] = []

    @abstractmethod
    def get_criteria(self) -> list[Criterion]:
        """Retorna la lista de criterios para este tipo de output."""
        pass

    @abstractmethod
    def evaluate_criterion_objective(self, criterion: Criterion, output: Any) -> CriterionResult:
        """Evalúa un criterio objetivo específico."""
        pass

    @abstractmethod
    def get_subjective_prompt(self, criterion: Criterion, output: Any) -> str:
        """Genera el prompt para evaluación subjetiva de un criterio."""
        pass

    def evaluate_objective(self, output: Any) -> list[CriterionResult]:
        """Evalúa todos los criterios objetivos."""
        results = []
        for criterion in self.get_criteria():
            if criterion.criterion_type == "objective":
                result = self.evaluate_criterion_objective(criterion, output)
                results.append(result)
        return results

    def evaluate_subjective(self, output: Any) -> list[CriterionResult]:
        """Evalúa todos los criterios subjetivos usando Claude Haiku."""
        results = []
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            # Sin API key, asumimos que pasan los criterios subjetivos con score 0.8
            for criterion in self.get_criteria():
                if criterion.criterion_type == "subjective":
                    results.append(CriterionResult(
                        name=criterion.name,
                        criterion_type="subjective",
                        weight=criterion.weight,
                        passed=True,
                        score=0.8,
                        reason="Sin API key - evaluación subjetiva omitida"
                    ))
            return results

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        for criterion in self.get_criteria():
            if criterion.criterion_type == "subjective":
                prompt = self.get_subjective_prompt(criterion, output)

                try:
                    message = client.messages.create(
                        model=self.subjective_model,
                        max_tokens=256,
                        messages=[{"role": "user", "content": prompt}]
                    )

                    response = message.content[0].text.strip()
                    score, reason = self._parse_subjective_response(response)

                    results.append(CriterionResult(
                        name=criterion.name,
                        criterion_type="subjective",
                        weight=criterion.weight,
                        passed=score >= 0.7,  # Umbral interno para criterios individuales
                        score=score,
                        reason=reason
                    ))
                except Exception as e:
                    # Si falla la evaluación, asumimos score bajo
                    results.append(CriterionResult(
                        name=criterion.name,
                        criterion_type="subjective",
                        weight=criterion.weight,
                        passed=False,
                        score=0.5,
                        reason=f"Error en evaluación: {str(e)}"
                    ))

        return results

    def _parse_subjective_response(self, response: str) -> tuple[float, str]:
        """Parsea la respuesta de evaluación subjetiva."""
        # Buscar score numérico (0-10 o 0-100 o 0.0-1.0)
        score_match = re.search(r"(?:score|puntaje|rating)[:\s]*(\d+(?:\.\d+)?)", response.lower())
        if score_match:
            score = float(score_match.group(1))
            if score > 1:
                score = score / 10 if score <= 10 else score / 100
        else:
            # Buscar cualquier número al inicio
            num_match = re.search(r"^(\d+(?:\.\d+)?)", response.strip())
            if num_match:
                score = float(num_match.group(1))
                if score > 1:
                    score = score / 10 if score <= 10 else score / 100
            else:
                score = 0.7  # Default

        # Limitar entre 0 y 1
        score = max(0.0, min(1.0, score))

        # Extraer razón (todo después del score)
        reason = response.strip()

        return score, reason

    def evaluate(self, output: Any) -> EvaluationResult:
        """Evalúa un output completo (objetiva + subjetiva)."""
        objective_results = self.evaluate_objective(output)
        subjective_results = self.evaluate_subjective(output)

        all_results = objective_results + subjective_results

        # Calcular scores
        total_score = sum(r.score * r.weight for r in all_results)
        max_score = sum(r.weight for r in all_results)
        percentage = total_score / max_score if max_score > 0 else 0

        # Determinar si pasa
        passed = percentage >= self.threshold

        # Separar criterios fallidos
        failed = [r for r in all_results if not r.passed]

        # Generar feedback
        feedback = self._generate_feedback(failed)

        return EvaluationResult(
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            threshold=self.threshold,
            passed=passed,
            criteria=all_results,
            failed_criteria=failed,
            feedback=feedback
        )

    def _generate_feedback(self, failed_criteria: list[CriterionResult]) -> str:
        """Genera feedback basado en criterios fallidos."""
        if not failed_criteria:
            return "Todos los criterios pasaron."

        lines = ["Criterios que necesitan mejora:"]
        for c in failed_criteria:
            reason = f" - {c.reason}" if c.reason else ""
            lines.append(f"- {c.name} (score: {c.score:.2f}){reason}")

        return "\n".join(lines)


def detect_language_english(text: str) -> bool:
    """Detecta si el texto está mayormente en inglés."""
    # Palabras comunes en inglés
    english_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can",
        "of", "to", "in", "for", "on", "with", "at", "by", "from",
        "and", "or", "but", "not", "no", "yes", "this", "that",
        "it", "its", "as", "if", "when", "where", "how", "what",
        "who", "which", "vintage", "nostalgic", "warm", "soft"
    }

    # Palabras comunes en español
    spanish_words = {
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "de", "del", "al", "en", "con", "por", "para", "sobre",
        "es", "son", "era", "eran", "fue", "fueron", "ser", "estar",
        "y", "o", "pero", "sino", "que", "como", "cuando", "donde",
        "este", "esta", "estos", "estas", "ese", "esa", "aquel",
        "yo", "tu", "el", "ella", "nosotros", "ustedes", "ellos"
    }

    words = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))

    english_count = len(words & english_words)
    spanish_count = len(words & spanish_words)

    # Consideramos inglés si tiene más palabras en inglés que en español
    return english_count > spanish_count
