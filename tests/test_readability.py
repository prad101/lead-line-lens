import textstat

from app.ui import PRIVACY_NOTE
from lll.predict import explain

MAX_GRADE = 8.0


def test_privacy_note_reading_level():
    assert textstat.flesch_kincaid_grade(PRIVACY_NOTE) <= MAX_GRADE


def test_shap_reasons_reading_level():
    reasons = explain(
        {"year_built": 0.4, "nbr_lead_share_k10": 0.2, "utility_side_material": -0.1},
        {"year_built": 1912, "nbr_lead_share_k10": 0.8, "utility_side_material": "Lead"},
    )
    text = " ".join(reasons)
    assert textstat.flesch_kincaid_grade(text) <= MAX_GRADE
