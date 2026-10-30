from fastapi import APIRouter
from pydantic import BaseModel

from api.routers import not_implemented

router = APIRouter(tags=["predict"])


class PredictRequest(BaseModel):
    address: str | None = None
    features: dict[str, float | int | str | None] | None = None


@router.post("/predict", summary="Calibrated prediction for an unknown line")
def predict(req: PredictRequest):
    """Calibrated probability of lead/GRR, confidence tier, three reasons, model version."""
    raise not_implemented("Gate 3")
