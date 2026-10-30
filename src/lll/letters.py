"""Verification and prioritization request letters.

Rendered in memory from Jinja2 templates; nothing is written to disk or logged.
The letter is a template the resident edits and sends, not legal advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LetterContext:
    address: str
    ward: int | None
    utility_side_material: str
    customer_side_material: str
    probability_lead: float | None = None
    tier: str | None = None
    child_or_pregnancy: bool = False
    has_filter: str = "unknown"
    notified: str = "unsure"
    tenure: str = "own"
    requests: list[str] = field(default_factory=list)


def render_letter(ctx: LetterContext, template: str = "verification_request.j2") -> str:
    """Render the letter body as plain text.

    TODO: implement (Gate 3).
    """
    raise NotImplementedError


def to_docx(text: str) -> bytes:
    """Return a .docx document of the letter as bytes.

    TODO: implement (Gate 3).
    """
    raise NotImplementedError


def mailto_link(to: str, subject: str, body: str, cc: str | None = None) -> str:
    """Build a mailto: URL with subject and body pre-filled.

    TODO: implement (Gate 3).
    """
    raise NotImplementedError
