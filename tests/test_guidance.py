import textstat

from lll.guidance import (
    PRIMARY_CLICKS,
    SURVEY_QUESTIONS,
    plan_for,
    plan_text,
    status_plain,
)
from lll.predict import TREAT_AS_LEAD_MESSAGE

MAX_GRADE = 8.0


def _plan(**kwargs):
    base = dict(
        line_status="Unknown", utility_side="Unknown", customer_side="Unknown",
        child_or_pregnancy=True, has_filter="no", notified="no", tenure="rent",
        tested="no",
    )
    base.update(kwargs)
    return plan_for(**base)


def test_flow_is_at_most_five_primary_clicks():
    assert 1 <= len(PRIMARY_CLICKS) <= 5
    assert len(SURVEY_QUESTIONS) == 5


def test_every_health_statement_has_an_https_source():
    items = _plan()
    health = [i for i in items if i.health]
    assert health, "expected health guidance"
    for item in health:
        assert item.source_url and item.source_url.startswith("https://"), item
        assert item.source_label


def test_unknown_never_reads_as_safe():
    text = plan_text(_plan()).lower()
    assert TREAT_AS_LEAD_MESSAGE.lower() in text
    assert "safe" not in text
    assert "not lead" not in text or "possibly lead" in text


def test_known_nonlead_does_not_call_the_line_safe():
    items = _plan(line_status="Non-Lead", utility_side="Non-Lead", customer_side="Non-Lead")
    text = plan_text(items).lower()
    assert "records can be wrong" in text
    assert "safe" not in text
    assert TREAT_AS_LEAD_MESSAGE.lower() not in text


def test_prediction_does_not_drop_treat_as_lead_for_unknown():
    items = _plan(line_status="Unknown", customer_side="Unknown")
    assert any(i.text == TREAT_AS_LEAD_MESSAGE for i in items)


def test_guidance_and_questions_are_grade_eight_or_easier():
    items = _plan()
    blob = plan_text(items) + " " + " ".join(SURVEY_QUESTIONS)
    assert textstat.flesch_kincaid_grade(blob) <= MAX_GRADE
    for q in SURVEY_QUESTIONS:
        assert textstat.flesch_kincaid_grade(q) <= MAX_GRADE


def test_status_plain_labels():
    assert status_plain("Lead") == "Lead"
    assert "possibly lead" in status_plain("Unknown").lower()
    assert "Galvanized" in status_plain("GRR")
    assert "records" in status_plain("Non-Lead").lower()


def test_owner_with_filter_and_a_tap_test():
    from lll.guidance import markdown

    items = _plan(
        line_status="Lead", utility_side="Lead", customer_side="Lead",
        child_or_pregnancy=False, has_filter="yes", notified="yes",
        tenure="own", tested="yes",
    )
    text = plan_text(items).lower()
    assert "lead or galvanized" in text
    assert "keep using" in text
    assert "tap test" in text
    assert "free pipe replacement" in text
    linked = markdown(items[0]) if items[0].source_url else markdown(
        next(i for i in items if i.source_url)
    )
    assert "](https://" in linked
