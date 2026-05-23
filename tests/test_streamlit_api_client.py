from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


API_CLIENT_PATH = Path(__file__).resolve().parents[1] / "client" / "streamlit" / "api_client.py"
spec = importlib.util.spec_from_file_location("streamlit_api_client", API_CLIENT_PATH)
api_client = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(api_client)


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_build_url_uses_base_url_without_double_slashes() -> None:
    assert api_client.build_url("/health", "http://example.test/") == "http://example.test/health"


def test_handle_response_returns_json_payload() -> None:
    assert api_client.handle_response(FakeResponse(200, {"status": "ok"})) == {"status": "ok"}


def test_handle_response_raises_for_non_200_response() -> None:
    with pytest.raises(api_client.APIClientError) as exc:
        api_client.handle_response(FakeResponse(404, {"detail": "Missing"}))

    assert exc.value.status_code == 404
    assert "Missing" in str(exc.value)
