from __future__ import annotations

from datetime import datetime


def create_run_id() -> str:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    return f"run-{timestamp}"
