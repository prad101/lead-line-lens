import textstat

from app.ui import PRIVACY_NOTE

MAX_GRADE = 8.0


def test_privacy_note_reading_level():
    assert textstat.flesch_kincaid_grade(PRIVACY_NOTE) <= MAX_GRADE
