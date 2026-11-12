from pathlib import Path

from lll import METHODOLOGY_URL

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "app" / "Home.py", *sorted((ROOT / "app" / "pages").glob("*.py"))]


def test_every_page_renders_the_methodology_footer():
    assert len(PAGES) >= 5
    for page in PAGES:
        assert "footer()" in page.read_text(), f"{page.name} has no footer"


def test_methodology_link_points_to_a_finished_doc():
    assert METHODOLOGY_URL.endswith("docs/methodology.md")
    text = (ROOT / "docs" / "methodology.md").read_text()
    assert "Draft" not in text
    for section in ("## Data sources", "## Small-cell suppression", "## Disparity measures",
                    "## Limitations"):
        assert section in text
