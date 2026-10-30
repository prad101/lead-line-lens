from fastapi import APIRouter, UploadFile

from api.routers import not_implemented

router = APIRouter(prefix="/utility", tags=["utility edition"])


@router.post("/upload", summary="Upload an inventory CSV/XLSX")
async def upload(file: UploadFile):
    raise not_implemented("Gate 6")


@router.post("/map", summary="Map uploaded columns to the canonical schema")
def map_columns():
    raise not_implemented("Gate 6")


@router.post("/classify", summary="Train fresh or transfer the Chicago model")
def classify():
    raise not_implemented("Gate 6")


@router.post("/sample-plan", summary="Stratified verification sampling plan")
def sample_plan():
    raise not_implemented("Gate 6")


@router.post("/export", summary="Illinois EPA template export and methods memo")
def export():
    raise not_implemented("Gate 6")
