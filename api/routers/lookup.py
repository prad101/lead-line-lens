from fastapi import APIRouter, Query

from api.routers import not_implemented

router = APIRouter(tags=["lookup"])


@router.get("/lookup", summary="Recorded service line status for an address")
def lookup(address: str = Query(..., min_length=3, description="Street address in Chicago")):
    """Utility-side and customer-side material, verification method, replacement status,
    snapshot date, and block/tract/ward/community area."""
    raise not_implemented("Gate 3")
