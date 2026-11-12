from pathlib import Path

import httpx
import pytest

from app import api_client
from app.api_client import ApiError
from lll.guidance import LETTER_BUTTON, LOOKUP_BUTTON, PLAN_BUTTON, PRIMARY_CLICKS

LOOKUP_PAGE = Path(__file__).resolve().parents[1] / "app" / "pages" / "lookup.py"
THEME = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"


def test_lookup_page_uses_the_three_primary_clicks_and_no_wide_layout():
    src = LOOKUP_PAGE.read_text()
    assert "LOOKUP_BUTTON" in src and "PLAN_BUTTON" in src and "LETTER_BUTTON" in src
    assert 'layout="centered"' in src
    assert 'layout="wide"' not in src
    assert "cache_data" not in src
    assert LOOKUP_BUTTON and PLAN_BUTTON and LETTER_BUTTON
    assert len(PRIMARY_CLICKS) <= 5


def test_lookup_page_renders_source_links_from_guidance():
    src = LOOKUP_PAGE.read_text()
    assert "markdown(item)" in src
    assert "fetch_letter" in src
    assert "PRIVACY_NOTE" in src
    assert "LEGAL_NOTE" in src


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    L1, L2 = _lum(a), _lum(b)
    lighter, darker = max(L1, L2), min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)


def test_theme_colors_meet_wcag_aa():
    colors = {}
    for line in THEME.read_text().splitlines():
        if "=" not in line or line.strip().startswith("["):
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"')
        if value.startswith("#"):
            colors[key.strip()] = value
    assert _contrast(colors["textColor"], colors["backgroundColor"]) >= 4.5
    assert _contrast(colors["primaryColor"], colors["backgroundColor"]) >= 4.5
    assert _contrast(colors["textColor"], colors["secondaryBackgroundColor"]) >= 4.5


def test_api_client_lookup_and_errors(monkeypatch):
    class Ok(httpx.Response):
        def __init__(self):
            super().__init__(
                200, json={"normalized": "123 N MAIN ST", "n_lines": 1, "lines": []},
            )

    monkeypatch.setattr(httpx, "request", lambda *a, **k: Ok())
    body = api_client.lookup("123 N Main")
    assert body["normalized"] == "123 N MAIN ST"

    class Missing(httpx.Response):
        def __init__(self):
            super().__init__(
                404, json={"detail": "No service line found for that address."},
            )

    monkeypatch.setattr(httpx, "request", lambda *a, **k: Missing())
    with pytest.raises(ApiError) as err:
        api_client.lookup("999 Nowhere")
    assert err.value.status_code == 404
    assert "No service line" in err.value.detail
