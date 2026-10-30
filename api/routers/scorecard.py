from fastapi import APIRouter, Path

from api.routers import not_implemented

router = APIRouter(tags=["scorecard"])


@router.get("/scorecard/ward/{ward}.pdf", summary="One-page ward scorecard PDF")
def ward_scorecard(ward: int = Path(..., ge=1, le=50)):
    raise not_implemented("Gate 5")
