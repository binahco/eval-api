from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from llm_client import TokenUsage
from llm_client.provider import ProviderRequest, ProviderResponse

from eval_api.main import DEFAULT_DATASET, create_app


class StubProvider:
    name = "stub"

    def __init__(self, text: str) -> None:
        self.text = text
        self.usage = TokenUsage(input_tokens=10, output_tokens=5)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(text=self.text, model=request.model, usage=self.usage)

    def stream(self, request: ProviderRequest):
        yield self.text


def test_health_reusa_web_api_base() -> None:
    app = create_app(provider=StubProvider("texto"))
    body = TestClient(app).get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "eval-api"
    assert body["provider"] == "stub"
    assert body["week"] == 6


def test_llm_endpoint_de_la_base_disponible() -> None:
    app = create_app(provider=StubProvider('{"summary": "x", "risk": "none", "verdict": "pass", "actions": []}'))
    resp = TestClient(app).post(
        "/llm",
        json={
            "prompt_id": "eval-summarizer",
            "variables": {"report": "r", "modo": "json"},
            "response_schema": "eval-summary-v1",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["validation_ok"] is True
    assert resp.json()["parsed"]["verdict"] == "pass"


def test_evals_run_corre_test_kit_sobre_dataset() -> None:
    app = create_app(provider=StubProvider("texto"))
    resp = TestClient(app).post("/evals/run", json={"dataset": str(DEFAULT_DATASET), "mode": "full", "threshold": 1.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["prompt_id"] == "eval-summarizer"
    assert body["total"] == 3
    assert body["mode"] == "full"


def test_evals_run_dataset_invalido_422() -> None:
    app = create_app(provider=StubProvider("texto"))
    resp = TestClient(app).post("/evals/run", json={"dataset": str(DEFAULT_DATASET.parent / "no-existe.jsonl")})
    assert resp.status_code == 422
    assert resp.json()["error"] == "dataset_invalido"


def test_summarize_devuelve_resumen_validado() -> None:
    app = create_app(
        provider=StubProvider('{"summary": "3 de 4 casos pasan", "risk": "moderate", "verdict": "fail", "actions": ["revisar caso 3"]}')
    )
    resp = TestClient(app).post("/summarize", json={"report": json.dumps({"total": 4, "passed": 3})})
    assert resp.status_code == 200
    body = resp.json()
    assert body["validation_ok"] is True
    assert body["parsed"]["verdict"] == "fail"