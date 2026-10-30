"""One-page ward scorecards rendered with Jinja2 and WeasyPrint.

Scorecards rank need for verification and replacement, never the reverse.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def ward_context(ward: int, ward_table: pd.DataFrame, blocks: pd.DataFrame) -> dict:
    """Build the template context for one ward.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def render_html(context: dict) -> str:
    """Render templates/scorecard.html.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def render_pdf(context: dict) -> bytes:
    """Render one scorecard to PDF bytes.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def generate_all(out_dir: str | Path) -> list[Path]:
    """Write all 50 ward scorecard PDFs.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError
