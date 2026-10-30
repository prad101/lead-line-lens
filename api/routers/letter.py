from fastapi import APIRouter
from pydantic import BaseModel

from api.routers import not_implemented

router = APIRouter(tags=["letter"])


class LetterRequest(BaseModel):
    address: str
    child_or_pregnancy: bool = False
    has_filter: str = "unknown"
    notified: str = "unsure"
    tenure: str = "own"


@router.post("/letter", summary="Render the verification and prioritization letter")
def letter(req: LetterRequest):
    """Plain text and .docx (base64), with a mailto payload. Rendered in memory only."""
    raise not_implemented("Gate 3")
