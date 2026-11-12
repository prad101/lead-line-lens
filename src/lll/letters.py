"""Verification and prioritization request letters.

Rendered in memory from Jinja2 templates; nothing is written to disk or logged.
The letter is a template the resident edits and sends, not legal advice.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import quote

from lll import TEMPLATE_DIR
from lll.predict import TREAT_AS_LEAD_MESSAGE

DWM_MAILTO = ""  # resident picks the recipient; we do not guess an inbox
DEFAULT_SUBJECT = "Service line verification request"
LEGAL_NOTE = "This letter is a request I can edit and send. It is not legal advice."
_NEEDS_REPLACE = ("Lead", "GRR", "Unknown")


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
    snapshot: str | None = None
    requests: list[str] = field(default_factory=list)
    lines: list[dict] = field(default_factory=list)


def _sides(ctx: LetterContext) -> list[str]:
    if ctx.lines:
        out = []
        for row in ctx.lines:
            out.append(str(row.get("utility_side_material") or "Unknown"))
            out.append(str(row.get("customer_side_material") or "Unknown"))
        return out
    return [ctx.utility_side_material, ctx.customer_side_material]


def default_requests(ctx: LetterContext) -> list[str]:
    """What the letter asks the city to do, in plain language."""
    items = ["Check this service line with a method Illinois EPA accepts."]
    if any(side in _NEEDS_REPLACE for side in _sides(ctx)):
        items.append("Replace the line if it is lead or galvanized, and tell me when.")
    if ctx.child_or_pregnancy:
        items.append("Give this home priority because a young child or pregnant person lives here.")
    if ctx.tenure == "rent":
        items.append("Send the result to me as well as to the owner.")
    if ctx.notified == "no":
        items.append("Tell me, in writing, that this line may be lead.")
    return items


def render_letter(ctx: LetterContext, template: str = "verification_request.j2") -> str:
    """Render the letter body as plain text."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR / "letters")),
                      autoescape=False, keep_trailing_newline=True)
    if not ctx.requests:
        ctx.requests = default_requests(ctx)
    today = dt.date.today().strftime("%B %d, %Y")
    text = env.get_template(template).render(
        today=today, address=ctx.address, ward=ctx.ward,
        utility_side_material=ctx.utility_side_material,
        customer_side_material=ctx.customer_side_material,
        probability_lead=ctx.probability_lead, tier=ctx.tier,
        child_or_pregnancy=ctx.child_or_pregnancy, has_filter=ctx.has_filter,
        notified=ctx.notified, tenure=ctx.tenure, snapshot=ctx.snapshot,
        requests=ctx.requests, treat_as_lead=TREAT_AS_LEAD_MESSAGE,
        lines=ctx.lines or [{
            "utility_side_material": ctx.utility_side_material,
            "customer_side_material": ctx.customer_side_material,
        }],
    )
    return "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"


def to_docx(text: str) -> bytes:
    """Return a .docx document of the letter as bytes."""
    from docx import Document

    doc = Document()
    for block in text.strip().split("\n\n"):
        p = doc.add_paragraph()
        lines = block.split("\n")
        p.add_run(lines[0] if lines else "")
        for line in lines[1:]:
            p.add_run().add_break()
            p.add_run(line)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def mailto_link(to: str, subject: str, body: str, cc: str | None = None) -> str:
    """Build a mailto: URL with subject and body pre-filled."""
    q = []
    if subject:
        q.append("subject=" + quote(subject, safe=""))
    if cc:
        q.append("cc=" + quote(cc, safe=""))
    if body:
        q.append("body=" + quote(body, safe=""))
    dest = to or ""
    return f"mailto:{dest}" + ("?" + "&".join(q) if q else "")
