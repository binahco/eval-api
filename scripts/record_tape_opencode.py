from pathlib import Path

from llm_client import CompletionRequest, CompletionResult, LlmClient, ReplayProvider
from llm_client.providers.opencode_cli import OpenCodeCLI
from test_kit import EvalCase, EvalDataset, run

from eval_api.main import DEFAULT_MODEL, SCHEMA_ID, build_client, judge_for

ROOT = Path(__file__).resolve().parents[1]
CASSETTES = ROOT / "cassettes"


def main() -> None:
    dataset = EvalDataset.from_jsonl(ROOT / "evals" / "eval-summarizer.jsonl")

    recorder = ReplayProvider(CASSETTES, record=True, inner=OpenCodeCLI(DEFAULT_MODEL))
    client = build_client(recorder)

    report = run(dataset, judge_for(client), mode="full", threshold=1.0)
    print(f"grabadas {len(dataset.cases)} respuestas; pass={report.passed}/{report.total}")
    for case_report in report.cases:
        print(case_report.model_dump())


if __name__ == "__main__":
    main()