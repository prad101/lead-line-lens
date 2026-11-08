from fastapi import APIRouter, HTTPException, Query

from api.schemas import LookupResponse
from api.serialize import line_record
from lll.geocode import normalize_address

router = APIRouter(tags=["lookup"])


@router.get(
    "/lookup",
    summary="Recorded service line status for an address",
    response_model=LookupResponse,
    responses={404: {"description": "No inventory row for that address"},
               400: {"description": "Address could not be parsed"},
               503: {"description": "Master table not loaded"}},
)
def lookup(address: str = Query(..., min_length=3, description="Street address in Chicago")):
    """Utility-side and customer-side material, verification method, replacement status,
    snapshot date, and block/tract/ward/community area.

    The address is not written to disk, a database, or the access log.
    """
    from api.store import get

    norm = normalize_address(address)
    if not norm:
        raise HTTPException(status_code=400, detail="Could not read that address.")
    try:
        store = get()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Inventory is not loaded yet.") from None
    rows = store.lookup(address)
    if rows.empty:
        raise HTTPException(status_code=404, detail="No service line found for that address.")
    lines = [line_record(r) for _, r in rows.iterrows()]
    snap = store.snapshot
    if len(snap) == 8 and snap.isdigit():
        snap = f"{snap[:4]}-{snap[4:6]}-{snap[6:]}"
    return LookupResponse(normalized=norm, snapshot=snap, n_lines=len(lines), lines=lines)
