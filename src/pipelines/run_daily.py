from __future__ import annotations

from pathlib import Path

from src.core.artifacts import write_brief, write_prompt_bundle
from src.core.logger import get_logger, log_event
from src.core.settings import load_pipeline_settings, load_prompts
from src.core.storage import prepare_run_dir
from src.agents.creative_director import CreativeInputs, create_brief


def run() -> Path:
    logger = get_logger()
    settings = load_pipeline_settings()
    prompts = load_prompts()

    run_dir = prepare_run_dir(settings.paths.runs_dir)
    log_event(logger, stage="init", status="ok", run_dir=str(run_dir))

    creative_inputs = CreativeInputs(settings=settings, prompts=prompts)
    brief = create_brief(creative_inputs)

    write_brief(run_dir / "brief.json", brief)
    log_event(logger, stage="artifact", status="ok", file="brief.json")

    write_prompt_bundle(run_dir / "prompt_bundle.json", prompts)
    log_event(logger, stage="artifact", status="ok", file="prompt_bundle.json")

    log_event(logger, stage="done", status="ok", run_dir=str(run_dir))
    return run_dir


if __name__ == "__main__":
    run()
