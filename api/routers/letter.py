import base64

from fastapi import APIRouter, HTTPException

from api.schemas import LetterRequest, LetterResponse
from lll.letters import (
    DEFAULT_SUBJECT,
    DWM_MAILTO,
    LetterContext,
    mailto_link,
    render_letter,
    to_docx,
)
from lll.train import FEATURES

router = APIRouter(tags=["letter"])


@router.post(
    "/letter",
    summary="Render the verification and prioritization letter",
    response_model=LetterResponse,
    responses={400: {"description": "Address could not be parsed"}},
)
def letter(req: LetterRequest):
    """Plain text and .docx (base64), with a mailto payload. Rendered in memory only."""
    from api.store import get
    from lll.geocode import normalize_address
    from lll.predict import predict_line

    if not normalize_address(req.address):
        raise HTTPException(status_code=400, detail="Could not read that address.")

    utility = customer = "Unknown"
    ward = None
    snap = None
    prob = None
    tier = None
    try:
        store = get()
        snap = store.snapshot
        rows = store.lookup(req.address)
        if not rows.empty:
            r = rows.iloc[0]
            utility = str(r.get("utility_side_material") or "Unknown")
            customer = str(r.get("customer_side_material") or "Unknown")
            from api.serialize import cell as _cell
            w = _cell(r.get("ward"))
            ward = int(w) if w is not None else None
            if customer not in ("Lead", "GRR", "Non-Lead") and store.model is not None:
                feats = {c: r[c] if c in r.index else None for c in FEATURES}
                pred = predict_line(feats, model=store.model)
                prob, tier = pred.probability_lead, pred.tier
        if snap and len(snap) == 8 and snap.isdigit():
            snap = f"{snap[:4]}-{snap[4:6]}-{snap[6:]}"
    except FileNotFoundError:
        store = None  # letter still renders from the address alone

    ctx = LetterContext(
        address=req.address, ward=ward, utility_side_material=utility,
        customer_side_material=customer, probability_lead=prob, tier=tier,
        child_or_pregnancy=req.child_or_pregnancy, has_filter=req.has_filter,
        notified=req.notified, tenure=req.tenure, snapshot=snap,
    )
    text = render_letter(ctx)
    subject = f"{DEFAULT_SUBJECT}: {req.address}"
    return LetterResponse(
        text=text,
        docx_base64=base64.b64encode(to_docx(text)).decode("ascii"),
        mailto=mailto_link(DWM_MAILTO, subject, text),
        subject=subject,
    )
