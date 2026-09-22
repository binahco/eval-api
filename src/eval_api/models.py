from __future__ import annotations

from pydantic import BaseModel, Field


class EvalSummary(BaseModel):
    """Schema eval-summary-v1: resumen humano de una corrida de evals (test-kit)."""

    summary: str
    risk: str
    verdict: str
    actions: list[str] = Field(default_factory=list)