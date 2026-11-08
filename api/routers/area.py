from typing import Literal

from fastapi import APIRouter, HTTPException

from api.schemas import AreaResponse
from api.serialize import cell

router = APIRouter(tags=["area"])

SKIP = {"geometry"}


@router.get(
    "/area/{level}/{area_id}",
    summary="Aggregates for an area, with suppression flags",
    response_model=AreaResponse,
    responses={404: {"description": "Unknown area"},
               503: {"description": "Aggregates not loaded"}},
)
def area(level: Literal["block", "tract", "ward", "community_area"], area_id: str):
    """Counts and shares by material, replaced share, predicted lead among unknowns,
    ACS joins, and suppression flags (cells under 5 lines are suppressed).
    """
    from api.store import get

    try:
        store = get()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Inventory is not loaded yet.") from None
    row = store.area(level, area_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No published numbers for that area.")
    values = {str(k): cell(v) for k, v in row.items() if str(k) not in SKIP}
    suppressed = bool(values.get("suppressed") or False)
    snap = store.snapshot
    if len(snap) == 8 and snap.isdigit():
        snap = f"{snap[:4]}-{snap[4:6]}-{snap[6:]}"
    return AreaResponse(level=level, area_id=str(area_id), snapshot=snap,
                        suppressed=suppressed, values=values)
