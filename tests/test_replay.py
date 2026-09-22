import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASSETTES = ROOT / "cassettes"

pytestmark = pytest.mark.skipif(
    not CASSETTES.exists() or not list(CASSETTES.glob("*.jsonl")),
    reason="sin cassettes: corre scripts/record_tape_opencode.py",
)


def test_cli_replay_verde() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "eval_api.main", "--replay", str(CASSETTES), "--mode", "full"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"threshold_ok": true' in proc.stdout
    assert '"total": 3' in proc.stdout
    assert '"passed": 3' in proc.stdout


def test_cli_replay_dataset_invalido() -> None:
    bad = ROOT / "evals" / "dataset_inexistente.jsonl"
    proc = subprocess.run(
        [sys.executable, "-m", "eval_api.main", "--dataset", str(bad), "--replay", str(CASSETTES)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "dataset inválido" in proc.stderr


def test_cli_replay_mismatch_dataset_prompt() -> None:
    tampered = ROOT / "evals" / "tmp_mismatch.jsonl"
    tampered.write_text(
        '{"prompt_id": "otro-prompt", "prompt_version": "9.9.9", "input": {}, "expected": null, "criteria": {"type": "schema_match", "schema": "eval-summary-v1"}}\n'
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "eval_api.main", "--dataset", str(tampered), "--replay", str(CASSETTES)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2
        assert "referencia" in proc.stderr
    finally:
        tampered.unlink(missing_ok=True)