from typing import Literal

from fastapi import APIRouter

from api.routers import not_implemented

router = APIRouter(tags=["area"])


@router.get("/area/{level}/{area_id}", summary="Aggregates for an area, with suppression flags")
def area(level: Literal["block", "tract", "ward", "community_area"], area_id: str):
    """Counts and shares by material, replaced share, predicted lead among unknowns,
    ACS joins, and suppression flags (cells under 5 lines are suppressed)."""
    raise not_implemented("Gate 3")
