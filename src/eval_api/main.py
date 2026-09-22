from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from llm_client import CompletionRequest, CompletionResult, LlmClient, ReplayProvider, Span
from llm_client.providers.opencode_cli import OpenCodeCLI
from schema_validate import SchemaRegistry
from test_kit import DatasetError, EvalCase, EvalDataset, run
from web_api_base import create_app as make_web_app
from web_api_base import llm_complete

from .models import EvalSummary

DEFAULT_MODEL = "opencode/big-pickle"
SCHEMA_ID = "eval-summary-v1"
ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "prompts"
DEFAULT_PROMPT = PROMPT_DIR / "eval-summarizer.md"
DEFAULT_DATASET = ROOT / "evals" / "eval-summarizer.jsonl"


def load_prompt(path: Path) -> tuple[str, str, str, Path]:
    text = path.read_text()
    if not text.startswith("---"):
        raise SystemExit(f"{path}: falta frontmatter")
    _, frontmatter, body = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    eval_path = ROOT / data["eval"] if not Path(data["eval"]).is_absolute() else Path(data["eval"])
    return data["id"], data["version"], body.strip(), eval_path


def render_prompt(prompt_id: str, prompt_version: str, variables: dict) -> list[dict]:
    _, _, body, _ = load_prompt(DEFAULT_PROMPT)
    system_part = body.split("## Sistema\n", 1)[1].split("## Usuario\n", 1)[0].strip()
    user_part = body.split("## Usuario\n", 1)[1].strip().format(
        report=variables["report"],
        modo=variables["modo"],
    )
    return [
        {"role": "system", "content": system_part},
        {"role": "user", "content": user_part},
    ]


def build_emitter(span_file: Path | None):
    def emit(span: Span, _result) -> None:
        if span_file is not None:
            with span_file.open("a") as handle:
                handle.write(span.as_jsonl() + "\n")
        else:
            sys.stderr.write(span.as_jsonl() + "\n")

    return emit


def build_client(provider, *, span_file: Path | None = None) -> LlmClient:
    registry = SchemaRegistry()
    registry.register(SCHEMA_ID, EvalSummary)
    return LlmClient(
        provider,
        consumer_repo="eval-api",
        model_aliases={"fast": DEFAULT_MODEL},
        validator=registry.make_validator(SCHEMA_ID),
        renderer=render_prompt,
        emitter=build_emitter(span_file),
    )


def judge_for(client: LlmClient) -> Callable[[EvalCase], CompletionResult]:
    def judge(case: EvalCase) -> CompletionResult:
        return client.complete(
            CompletionRequest(
                prompt_id=case.prompt_id,
                prompt_version=case.prompt_version,
                variables=case.input,
                model_alias="fast",
                response_schema=SCHEMA_ID if case.input.get("modo") == "json" else None,
                tags=["eval-api", "week-6"],
            )
        )

    return judge


class RunEvalsRequest(BaseModel):
    dataset: str | None = None
    mode: str = "smoke"
    threshold: float = 1.0


class SummarizeRequest(BaseModel):
    report: str


def create_app(*, provider, title: str = "eval-api", version: str = "0.1.0") -> FastAPI:
    """App FastAPI: web-api-base + test-kit expuesto por HTTP."""
    client = build_client(provider)
    app = make_web_app(
        title,
        version,
        client=client,
        health_extra={"week": 6},
    )

    @app.post("/evals/run", tags=["evals"])
    async def evals_run(req: RunEvalsRequest):
        dataset_path = Path(req.dataset) if req.dataset else DEFAULT_DATASET
        try:
            dataset = EvalDataset.from_jsonl(dataset_path)
        except DatasetError as exc:
            from web_api_base import LLMHTTPError

            raise LLMHTTPError(422, "dataset_invalido", detail=str(exc)) from exc
        report = run(dataset, judge_for(client), mode=req.mode, threshold=req.threshold)
        return report.model_dump(mode="json")

    @app.post("/summarize", tags=["evals"])
    async def summarize(req: SummarizeRequest):
        from web_api_base import CompleteRequest

        return llm_complete(
            client,
            CompleteRequest(
                prompt_id="eval-summarizer",
                prompt_version="0.1.0",
                variables={"report": req.report, "modo": "json"},
                model_alias="fast",
                response_schema=SCHEMA_ID,
                tags=["eval-api", "summarize"],
            ),
        )

    return app


def _run_eval(args) -> int:
    prompt_id, prompt_version, _, eval_path = load_prompt(DEFAULT_PROMPT)
    dataset_path = Path(args.dataset) if args.dataset else eval_path

    try:
        dataset = EvalDataset.from_jsonl(dataset_path)
    except DatasetError as exc:
        sys.stderr.write(f"eval-api: dataset inválido: {exc}\n")
        return 2

    if dataset.prompt_id != prompt_id or dataset.prompt_version != prompt_version:
        sys.stderr.write(
            f"eval-api: dataset referencia {dataset.prompt_id}@{dataset.prompt_version}, "
            f"el prompt es {prompt_id}@{prompt_version}\n"
        )
        return 2

    if args.replay:
        provider = ReplayProvider(args.replay, record=False)
    elif args.record:
        provider = ReplayProvider(args.record, record=True, inner=OpenCodeCLI(args.model))
    else:
        provider = OpenCodeCLI(args.model)

    client = build_client(provider, span_file=Path(args.span_file) if args.span_file else None)
    report = run(dataset, judge_for(client), mode=args.mode, threshold=args.threshold)
    print(report.model_dump_json(indent=2))

    if not report.threshold_ok:
        sys.stderr.write(f"eval-api: REGRESIÓN — {report.passed}/{report.total} casos pasan (umbral {args.threshold})\n")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval-api", description="Evals de prompts servidos por HTTP (test-kit + web-api-base).")
    parser.add_argument("--dataset", default=None, help="dataset .jsonl (default: el del frontmatter del prompt)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"modelo opencode (default: {DEFAULT_MODEL})")
    parser.add_argument("--replay", metavar="DIR", default=None, help="reproducir cassettes sin tocar el LLM")
    parser.add_argument("--record", metavar="DIR", default=None, help="grabar cassettes reales (record)")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke", help="smoke: diario · full: releases")
    parser.add_argument("--threshold", type=float, default=1.0, help="fracción mínima de casos en verde [0,1]")
    parser.add_argument("--span-file", metavar="PATH", default=None, help="escribir spans a JSONL")
    args = parser.parse_args(argv)
    return _run_eval(args)


if __name__ == "__main__":
    raise SystemExit(main())