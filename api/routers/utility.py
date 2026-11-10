import base64
import datetime as dt
import json

from fastapi import APIRouter, HTTPException, UploadFile

from api.schemas import (
    UtilityCounts,
    UtilityExportResponse,
    UtilityJobRequest,
    UtilityMapRequest,
    UtilityUploadResponse,
)
from lll.ingest import map_columns, suggest_mapping
from lll.schema import validate_inventory
from lll.utility import (
    classify,
    export_il_epa_template,
    methods_memo,
    stratified_sample_plan,
    summarize,
    utility_edition_enabled,
)

router = APIRouter(prefix="/utility", tags=["utility edition"])


def _job(job_id: str) -> dict:
    from api import jobs

    try:
        return jobs.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown job. Upload the file again.") from None


def _require() -> None:
    if not utility_edition_enabled():
        raise HTTPException(status_code=403, detail="Utility edition is turned off.")


@router.post("/upload", summary="Upload an inventory CSV/XLSX",
             response_model=UtilityUploadResponse)
async def upload(file: UploadFile):
    """Read the file in memory. It is not written to disk."""
    from api import jobs
    from lll.ingest import read_bytes

    _require()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The file was empty.")
    name = file.filename or "inventory.csv"
    try:
        raw = read_bytes(data, name)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    job_id = jobs.create(raw, name)
    cols = [str(c) for c in raw.columns]
    return UtilityUploadResponse(
        job_id=job_id, n_rows=len(raw), columns=cols,
        suggested_mapping=suggest_mapping(cols),
    )


@router.post("/map", summary="Map uploaded columns to the canonical schema",
             response_model=UtilityCounts)
def map_columns_route(req: UtilityMapRequest):
    _require()
    job = _job(req.job_id)
    mapping = req.mapping or suggest_mapping([str(c) for c in job["raw"].columns])
    snap = req.snapshot_date or dt.date.today().isoformat()
    try:
        mapped = validate_inventory(
            map_columns(job["raw"], mapping, snapshot_date=snap)
        )
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    job["mapped"] = mapped
    job["classified"] = None
    if req.system_name:
        job["system_name"] = req.system_name
    counts = summarize(mapped)
    return UtilityCounts(**counts)


@router.post("/classify", summary="Train fresh or transfer the Chicago model",
             response_model=UtilityCounts)
def classify_route(req: UtilityJobRequest):
    _require()
    job = _job(req.job_id)
    if job["mapped"] is None:
        raise HTTPException(status_code=400, detail="Map columns first.")
    scored, warning = classify(job["mapped"])
    job["classified"] = scored
    job["warning"] = warning
    counts = summarize(scored)
    counts["warning"] = warning
    return UtilityCounts(**counts)


@router.post("/sample-plan", summary="Stratified verification sampling plan")
def sample_plan(req: UtilityJobRequest):
    _require()
    job = _job(req.job_id)
    frame = job["classified"] if job["classified"] is not None else job["mapped"]
    if frame is None:
        raise HTTPException(status_code=400, detail="Map columns first.")
    sample = stratified_sample_plan(frame)
    job["sample"] = sample
    return {"n": int(len(sample)), "rows": json.loads(sample.to_json(orient="records"))}


@router.post("/export", summary="Illinois EPA template export and methods memo",
             response_model=UtilityExportResponse)
def export(req: UtilityJobRequest):
    _require()
    job = _job(req.job_id)
    frame = job["classified"] if job["classified"] is not None else job["mapped"]
    if frame is None:
        raise HTTPException(status_code=400, detail="Map columns first.")
    sample = job["sample"]
    if sample is None:
        sample = stratified_sample_plan(frame)
        job["sample"] = sample
    counts = summarize(frame)
    memo = methods_memo({
        "system_name": job.get("system_name"),
        "system_id": None,
        "run_date": dt.date.today().isoformat(),
        "n_rows": counts["n_rows"],
        "n_known": counts["n_known"],
        "n_unknown": counts["n_unknown"],
        "transfer_warning": job.get("warning"),
        "sample_n": int(len(sample)),
        "treat_as_lead": "Treat this line as lead until it is verified.",
    })
    raw = export_il_epa_template(frame)
    return UtilityExportResponse(
        csv_base64=base64.b64encode(raw).decode("ascii"),
        memo=memo,
        filename="il_epa_inventory_export.csv",
    )
