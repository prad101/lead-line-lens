"""In-memory utility-edition jobs. Uploads are never written to disk."""

from __future__ import annotations

from uuid import uuid4

import pandas as pd

_JOBS: dict[str, dict] = {}


def create(raw: pd.DataFrame, filename: str) -> str:
    job_id = str(uuid4())
    _JOBS[job_id] = {
        "filename": filename,
        "raw": raw,
        "mapped": None,
        "classified": None,
        "sample": None,
        "warning": None,
        "system_name": filename,
    }
    return job_id


def get(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        raise KeyError(job_id)
    return job


def reset() -> None:
    _JOBS.clear()
