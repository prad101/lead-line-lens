import textstat

from lll.letters import (
    LetterContext,
    default_requests,
    mailto_link,
    render_letter,
    to_docx,
)

MAX_GRADE = 8.0


def _ctx(**kwargs):
    base = dict(address="123 N Main St", ward=18, utility_side_material="Unknown",
                customer_side_material="Unknown", probability_lead=0.89, tier="High",
                child_or_pregnancy=True, has_filter="no", notified="no", tenure="rent",
                snapshot="2025-04-14")
    base.update(kwargs)
    return LetterContext(**base)


def test_letter_asks_for_check_and_never_calls_unknown_safe():
    text = render_letter(_ctx())
    assert "123 N Main St" in text
    assert "Unknown" in text
    assert "possibly lead" in text
    assert "89%" in text
    assert "pregnant" in text.lower() or "under 6" in text
    assert "not legal advice" in text.lower()
    assert "Check this service line" in text
    assert "renter" in text.lower() or "owner" in text


def test_letter_reading_level():
    text = render_letter(_ctx())
    assert textstat.flesch_kincaid_grade(text) <= MAX_GRADE


def test_docx_is_a_real_document():
    raw = to_docx(render_letter(_ctx()))
    assert raw[:2] == b"PK"
    assert len(raw) > 1000


def test_mailto_encodes_body_and_allows_empty_to():
    link = mailto_link("", "Hello", "line 1\nline 2")
    assert link.startswith("mailto:?")
    assert "subject=Hello" in link
    assert "%0A" in link or "%0a" in link


def test_default_requests_for_known_nonlead_skip_replace():
    ctx = _ctx(utility_side_material="Non-Lead", customer_side_material="Non-Lead",
               child_or_pregnancy=False, tenure="own", notified="unsure")
    items = default_requests(ctx)
    assert items == ["Check this service line with a method Illinois EPA accepts."]
