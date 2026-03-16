from __future__ import annotations

import json
import logging
from typing import Any


def get_logger(name: str = "oldies-tango") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_event(logger: logging.Logger, **payload: Any) -> None:
    logger.info(json.dumps(payload, ensure_ascii=False))
