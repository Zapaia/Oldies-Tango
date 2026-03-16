from __future__ import annotations

from pathlib import Path

from src.core.ids import create_run_id


def prepare_run_dir(base_dir: str = "data/runs") -> Path:
    run_id = create_run_id()
    run_dir = Path(base_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir
