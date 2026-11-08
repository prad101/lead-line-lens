from fastapi import APIRouter, HTTPException

from api.schemas import PredictRequest, PredictResponse
from lll.predict import TREAT_AS_LEAD_MESSAGE, predict_line
from lll.train import FEATURES

router = APIRouter(tags=["predict"])

_KNOWN_OK = ("Lead", "GRR", "Non-Lead")


@router.post(
    "/predict",
    summary="Calibrated prediction for an unknown line",
    response_model=PredictResponse,
    responses={400: {"description": "Need an address or a feature dict"},
               404: {"description": "No inventory row for that address"},
               503: {"description": "Model or inventory not loaded"}},
)
def predict(req: PredictRequest):
    """Calibrated probability of lead/GRR, confidence tier, three reasons, model version.

    A prediction never lowers urgency. Unknown is always possibly lead until verified.
    The address is not stored or logged.
    """
    from api.store import get

    if not req.address and not req.features:
        raise HTTPException(status_code=400, detail="Send an address or a feature dict.")
    try:
        store = get()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Inventory is not loaded yet.") from None
    if store.model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded yet.") from None

    recorded = None
    features = dict(req.features or {})
    if req.address:
        rows = store.lookup(req.address)
        if rows.empty:
            raise HTTPException(status_code=404, detail="No service line found for that address.")
        recorded = rows.iloc[0]
        if not req.features:
            features = {c: recorded[c] if c in recorded.index else None for c in FEATURES}

    customer = None if recorded is None else str(recorded.get("customer_side_material"))
    status = None if recorded is None else str(recorded.get("line_status"))
    if customer in _KNOWN_OK:
        if customer in ("Lead", "GRR"):
            msg = "City records list this line as lead or galvanized."
        else:
            msg = ("City records list this line as not lead. Records can be wrong; "
                   "you can still ask the city to check.")
        return PredictResponse(
            probability_lead=None, tier=None, reasons=[], model_version="v1",
            message=msg, customer_side_material=customer, line_status=status,
        )

    out = predict_line(features, model=store.model)
    return PredictResponse(
        probability_lead=out.probability_lead, tier=out.tier, reasons=out.reasons,
        model_version=out.model_version, message=TREAT_AS_LEAD_MESSAGE,
        customer_side_material=customer, line_status=status,
    )
