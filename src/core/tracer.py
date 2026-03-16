from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator


@dataclass
class Span:
    name: str
    started_at: str
    _start_ts: float = field(repr=False)
    finished_at: str | None = None
    duration_ms: float | None = None
    status: str = "ok"       # "ok" | "error" | "skipped"
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def _finish(self, status: str = "ok", error: str | None = None) -> None:
        end_ts = time.monotonic()
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.duration_ms = round((end_ts - self._start_ts) * 1000, 1)
        self.status = status
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        if self.error:
            d["error"] = self.error
        return d


class Tracer:
    """
    Registra spans (unidades de trabajo) dentro de un trace (run completo).

    Uso básico:
        tracer = Tracer(trace_id="run_2026-03-10")
        with tracer.span("creative_director", model="claude-sonnet-4"):
            ...
        tracer.save(run_dir)
    """

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._start_ts = time.monotonic()
        self.spans: list[Span] = []
        self.status: str = "ok"

    @contextmanager
    def span(self, name: str, **metadata: Any) -> Generator[Span, None, None]:
        """Context manager que mide duración y captura errores del bloque."""
        s = Span(
            name=name,
            started_at=datetime.now(timezone.utc).isoformat(),
            _start_ts=time.monotonic(),
            metadata=metadata,
        )
        self.spans.append(s)
        try:
            yield s
            s._finish(status="ok")
        except Exception as exc:
            s._finish(status="error", error=f"{type(exc).__name__}: {exc}")
            self.status = "error"
            raise

    def skip(self, name: str, reason: str = "") -> None:
        """Registra un span que fue saltado (sin ejecutar)."""
        s = Span(
            name=name,
            started_at=datetime.now(timezone.utc).isoformat(),
            _start_ts=time.monotonic(),
            status="skipped",
            metadata={"reason": reason} if reason else {},
        )
        s._finish(status="skipped")
        self.spans.append(s)

    def to_dict(self) -> dict[str, Any]:
        end_ts = time.monotonic()
        total_ms = round((end_ts - self._start_ts) * 1000, 1)
        return {
            "trace_id": self.trace_id,
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "total_duration_ms": total_ms,
            "status": self.status,
            "spans": [s.to_dict() for s in self.spans],
        }

    def save(self, run_dir: Path) -> Path:
        """Escribe trace.json en el run_dir y devuelve el path."""
        path = run_dir / "trace.json"
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
