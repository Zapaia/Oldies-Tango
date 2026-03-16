"""
Logger especializado para evaluaciones de agentes.

Guarda en dos lugares:
- {run_dir}/evaluations.json: evaluaciones de este run específico
- data/evaluations_history.jsonl: histórico global para análisis macro
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.evaluator import EvaluationResult, CriterionResult


def _criterion_to_dict(criterion: CriterionResult) -> dict:
    """Convierte un CriterionResult a dict."""
    return {
        "name": criterion.name,
        "type": criterion.criterion_type,
        "weight": criterion.weight,
        "passed": criterion.passed,
        "score": criterion.score,
        "reason": criterion.reason,
    }


def _evaluation_to_dict(
    result: EvaluationResult,
    agent: str,
    attempt: int,
    output_snapshot: Any = None
) -> dict:
    """Convierte un EvaluationResult a dict para logging."""
    return {
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "attempt": attempt,
        "total_score": round(result.total_score, 3),
        "max_score": round(result.max_score, 3),
        "percentage": round(result.percentage, 3),
        "threshold": result.threshold,
        "passed": result.passed,
        "criteria": [_criterion_to_dict(c) for c in result.criteria],
        "failed_criteria": [c.name for c in result.failed_criteria],
        "feedback": result.feedback,
        "output_snapshot": output_snapshot,
    }


class EvaluationLogger:
    """Logger para evaluaciones de agentes."""

    def __init__(self, run_dir: Path | None = None):
        self.run_dir = run_dir
        self.history_file = Path("data/evaluations_history.jsonl")
        self._evaluations: list[dict] = []

    def log_evaluation(
        self,
        result: EvaluationResult,
        agent: str,
        attempt: int,
        output_snapshot: Any = None
    ) -> dict:
        """
        Registra una evaluación.

        Args:
            result: Resultado de la evaluación
            agent: Nombre del agente (creative_director, music_agent)
            attempt: Número de intento (1, 2, ...)
            output_snapshot: Snapshot del output evaluado (opcional)

        Returns:
            El dict del log entry
        """
        entry = _evaluation_to_dict(result, agent, attempt, output_snapshot)
        self._evaluations.append(entry)

        # Guardar al histórico global (append)
        self._append_to_history(entry)

        # Log a consola
        status = "PASSED" if result.passed else "FAILED"
        print(f"[evaluator] {agent} attempt {attempt}: {status} ({result.percentage:.1%})")

        if not result.passed and result.failed_criteria:
            failed_names = [c.name for c in result.failed_criteria]
            print(f"[evaluator] Criterios fallidos: {failed_names}")

        return entry

    def _append_to_history(self, entry: dict) -> None:
        """Agrega una entrada al histórico global."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def save_to_run_dir(self) -> Path | None:
        """
        Guarda todas las evaluaciones de este run en el directorio del run.

        Returns:
            Path al archivo guardado, o None si no hay run_dir
        """
        if not self.run_dir:
            return None

        self.run_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.run_dir / "evaluations.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self._evaluations, f, indent=2, ensure_ascii=False)

        return output_path

    def get_summary(self) -> dict:
        """Retorna un resumen de las evaluaciones de este run."""
        if not self._evaluations:
            return {"total_evaluations": 0}

        passed = [e for e in self._evaluations if e["passed"]]
        failed = [e for e in self._evaluations if not e["passed"]]

        return {
            "total_evaluations": len(self._evaluations),
            "passed": len(passed),
            "failed": len(failed),
            "agents": list(set(e["agent"] for e in self._evaluations)),
            "average_score": sum(e["percentage"] for e in self._evaluations) / len(self._evaluations),
        }


def render_grid_html(evaluations: list[dict]) -> str:
    """
    Genera una tabla HTML con el historial de evaluaciones del run.

    Muestra una fila por criterio, agrupada por agente.
    Útil para incluir en el email de notificación.
    """
    if not evaluations:
        return ""

    rows = ""
    for eval_entry in evaluations:
        agent = eval_entry.get("agent", "?")
        attempt = eval_entry.get("attempt", 1)
        percentage = eval_entry.get("percentage", 0)
        criteria = eval_entry.get("criteria", [])

        agent_label = f"{agent} (intento {attempt})" if attempt > 1 else agent
        percentage_color = "#2ecc71" if percentage >= 0.9 else "#e74c3c" if percentage < 0.7 else "#f39c12"

        # Fila de cabecera del agente
        rows += f"""
            <tr style="background:#12122a;border-top:2px solid #1e1e40;">
                <td colspan="5" style="padding:6px 10px;font-size:12px;color:#c9a84c;font-weight:bold;letter-spacing:1px;text-transform:uppercase;">
                    {agent_label}
                    <span style="float:right;color:{percentage_color};font-size:13px;">{percentage:.0%}</span>
                </td>
            </tr>"""

        # Fila por criterio
        for c in criteria:
            passed = c.get("passed", False)
            score = c.get("score", 0.0)
            reason = c.get("reason") or ""
            ctype = c.get("type", "objective")
            name = c.get("name", "?")

            icon = "✓" if passed else "✗"
            icon_color = "#2ecc71" if passed else "#e74c3c"
            type_color = "#888" if ctype == "objective" else "#9b59b6"
            reason_html = f'<div style="font-size:11px;color:#e74c3c;margin-top:2px;">{reason}</div>' if not passed and reason else ""

            rows += f"""
            <tr style="border-bottom:1px solid #1a1a2e;">
                <td style="padding:5px 10px;color:#aaa;font-size:13px;">{name}{reason_html}</td>
                <td style="padding:5px 8px;text-align:center;font-size:11px;color:{type_color};">{ctype}</td>
                <td style="padding:5px 8px;text-align:right;color:#888;font-size:13px;">{score:.2f}</td>
                <td style="padding:5px 8px;text-align:center;font-weight:bold;color:{icon_color};font-size:15px;">{icon}</td>
            </tr>"""

    return f"""
    <div style="margin-top:24px;">
        <h3 style="font-family:Arial,sans-serif;color:#c9a84c;border-bottom:1px solid #222;padding-bottom:6px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">🔍 Grilla de evaluación</h3>
        <table style="width:100%;font-size:13px;border-collapse:collapse;font-family:Arial,sans-serif;">
            <thead>
                <tr style="color:#555;font-size:11px;border-bottom:1px solid #222;">
                    <th style="padding:4px 10px;text-align:left;">Criterio</th>
                    <th style="padding:4px 8px;text-align:center;">Tipo</th>
                    <th style="padding:4px 8px;text-align:right;">Score</th>
                    <th style="padding:4px 8px;text-align:center;">Estado</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>"""


def render_grid_text(evaluations: list[dict]) -> str:
    """
    Genera una representación de texto de la grilla de evaluaciones.
    Para logging en consola.
    """
    if not evaluations:
        return ""

    lines = ["\n── Grilla de evaluación ─────────────────────"]
    for eval_entry in evaluations:
        agent = eval_entry.get("agent", "?")
        attempt = eval_entry.get("attempt", 1)
        percentage = eval_entry.get("percentage", 0)
        criteria = eval_entry.get("criteria", [])

        label = f"{agent}" + (f" (intento {attempt})" if attempt > 1 else "")
        lines.append(f"\n  {label}: {percentage:.0%}")
        lines.append("  " + "─" * 50)

        for c in criteria:
            passed = c.get("passed", False)
            score = c.get("score", 0.0)
            name = c.get("name", "?")
            reason = c.get("reason") or ""

            mark = "✓" if passed else "✗"
            reason_str = f" → {reason}" if not passed and reason else ""
            lines.append(f"  [{mark}] {name:<35} {score:.2f}{reason_str}")

    lines.append("─" * 48)
    return "\n".join(lines)


def create_output_snapshot(output: Any) -> dict | None:
    """
    Crea un snapshot del output para logging.
    Intenta convertir a dict de forma segura.
    """
    if output is None:
        return None

    if isinstance(output, dict):
        return output

    if hasattr(output, "__dict__"):
        return {k: v for k, v in output.__dict__.items() if not k.startswith("_")}

    if hasattr(output, "_asdict"):  # namedtuple
        return output._asdict()

    # dataclass
    try:
        return asdict(output)
    except (TypeError, AttributeError):
        pass

    return {"raw": str(output)}
