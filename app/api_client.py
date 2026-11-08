"""HTTP client for the resident app. Addresses stay in the request only."""

from __future__ import annotations

import os

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text.strip() or f"Request failed ({response.status_code})."
    if isinstance(body, dict):
        err = body.get("detail", body)
        if isinstance(err, str):
            return err
    return f"Request failed ({response.status_code})."


def _send(method: str, path: str, **kwargs) -> dict:
    url = API_URL.rstrip("/") + path
    try:
        response = httpx.request(method, url, timeout=30.0, **kwargs)
    except httpx.ConnectError as err:
        raise ApiError(0, "The lookup service is not running.") from err
    except httpx.TimeoutException as err:
        raise ApiError(0, "The lookup service took too long to answer.") from err
    if response.status_code >= 400:
        raise ApiError(response.status_code, _detail(response))
    return response.json()


def lookup(address: str) -> dict:
    return _send("GET", "/lookup", params={"address": address})


def predict(address: str) -> dict:
    return _send("POST", "/predict", json={"address": address})


def letter(address: str, survey: dict) -> dict:
    payload = {
        "address": address,
        "child_or_pregnancy": bool(survey.get("child_or_pregnancy")),
        "has_filter": survey.get("has_filter", "unknown"),
        "notified": survey.get("notified", "unsure"),
        "tenure": survey.get("tenure", "own"),
    }
    return _send("POST", "/letter", json=payload)
