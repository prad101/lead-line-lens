from fastapi import APIRouter, UploadFile

from api.routers import not_implemented

router = APIRouter(prefix="/utility", tags=["utility edition"])

_GATE6 = {501: {"description": "Utility edition ships in Gate 6"}}


@router.post("/upload", summary="Upload an inventory CSV/XLSX", responses=_GATE6)
async def upload(file: UploadFile):
    raise not_implemented("Gate 6")


@router.post("/map", summary="Map uploaded columns to the canonical schema", responses=_GATE6)
def map_columns():
    raise not_implemented("Gate 6")


@router.post("/classify", summary="Train fresh or transfer the Chicago model", responses=_GATE6)
def classify():
    raise not_implemented("Gate 6")


@router.post("/sample-plan", summary="Stratified verification sampling plan", responses=_GATE6)
def sample_plan():
    raise not_implemented("Gate 6")


@router.post("/export", summary="Illinois EPA template export and methods memo", responses=_GATE6)
def export():
    raise not_implemented("Gate 6")
