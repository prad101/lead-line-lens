from typing import Literal

from pydantic import BaseModel, Field


class LineRecord(BaseModel):
    line_id: str | None = None
    address: str | None = None
    utility_side_material: str
    customer_side_material: str
    line_status: str
    verification_method: str | None = None
    replaced: bool | None = None
    replacement_date: str | None = None
    ward: str | None = None
    tract: str | None = None
    block: str | None = None
    community_area: str | None = None
    message: str | None = None


class LookupResponse(BaseModel):
    normalized: str
    snapshot: str
    n_lines: int
    lines: list[LineRecord]


class PredictRequest(BaseModel):
    address: str | None = None
    features: dict[str, float | int | str | None] | None = None


class PredictResponse(BaseModel):
    probability_lead: float | None
    tier: str | None
    reasons: list[str]
    model_version: str
    message: str
    customer_side_material: str | None = None
    line_status: str | None = None


class AreaResponse(BaseModel):
    level: str
    area_id: str
    snapshot: str
    suppressed: bool
    values: dict[str, float | int | str | None]


class LetterRequest(BaseModel):
    address: str = Field(..., min_length=3)
    child_or_pregnancy: bool = False
    has_filter: Literal["unknown", "yes", "no"] = "unknown"
    notified: Literal["unsure", "yes", "no"] = "unsure"
    tenure: Literal["own", "rent"] = "own"


class LetterResponse(BaseModel):
    text: str
    docx_base64: str
    mailto: str
    subject: str


class UtilityUploadResponse(BaseModel):
    job_id: str
    n_rows: int
    columns: list[str]
    suggested_mapping: dict[str, str]


class UtilityMapRequest(BaseModel):
    job_id: str
    mapping: dict[str, str] | None = None
    snapshot_date: str | None = None
    system_name: str | None = None


class UtilityJobRequest(BaseModel):
    job_id: str


class UtilityCounts(BaseModel):
    n_rows: int
    n_known: int
    n_unknown: int
    n_lead: int
    n_grr: int
    n_nonlead: int
    mean_p_unknown: float | None = None
    model_source: str | None = None
    warning: str | None = None


class UtilityExportResponse(BaseModel):
    csv_base64: str
    memo: str
    filename: str
