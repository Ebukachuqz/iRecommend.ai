from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import requests


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"

CATEGORIES = [
    "Health_and_Household",
    "Electronics",
    "Beauty_and_Personal_Care",
]

DEFAULT_CATEGORY = os.getenv("DEFAULT_CATEGORY", CATEGORIES[0])


class APIClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def get_api_base_url() -> str:
    return os.getenv("STREAMLIT_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


def build_url(path: str, base_url: str | None = None) -> str:
    base = (base_url or get_api_base_url()).rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def handle_response(response: requests.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise APIClientError(str(detail or "API request failed."), response.status_code, payload)
    return payload


def request_json(method: str, path: str, **kwargs: Any) -> Any:
    response = requests.request(method, build_url(path), timeout=60, **kwargs)
    return handle_response(response)


def get_health() -> dict[str, Any]:
    return request_json("GET", "/health")


def get_ready() -> dict[str, Any]:
    return request_json("GET", "/ready")


def list_users(category: str = DEFAULT_CATEGORY, limit: int = 20) -> list[dict[str, Any]]:
    return request_json("GET", "/users", params={"category": category, "limit": limit})


def get_persona(user_id: str, category: str = DEFAULT_CATEGORY) -> dict[str, Any]:
    return request_json("GET", f"/users/{user_id}/persona", params={"category": category})


def get_unseen_products(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return request_json("GET", f"/users/{user_id}/unseen-products", params={"limit": limit})


def simulate_review(payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", "/reviews/simulate", json=payload)


def generate_recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", "/recommendations/generate", json=payload)


def cold_start_recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", "/recommendations/cold-start", json=payload)


def session_message(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", f"/sessions/{session_id}/message", json=payload)
