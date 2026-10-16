"""Advisory model output. No settlement approvals or financial values live here."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
Lifecycle = Literal["pending", "fresh", "stale", "unavailable", "unconfigured", "disabled"]


class AdviceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Finding(AdviceModel):
    choice: Literal[
        "same_event",
        "different_event",
        "same_meaning",
        "different_meaning",
        "insufficient_evidence",
        "aligned",
        "inverted",
        "different_outcomes",
    ]
    confidence: Score
    probabilities: dict[str, Score]
    evidence_ids: tuple[str, ...] = ()


class EvidenceSpan(AdviceModel):
    id: str
    side: Literal["left", "right"]
    clause: str
    quotation: str
    artifact_id: str | None = None
    page: int | None = None
    start: int
    end: int
    applicability: str = "unverified"


class ClassificationSummary(AdviceModel):
    state: Lifecycle
    run_id: str | None = None
    input_hash: str | None = None
    event: Finding | None = None
    outcome_relation: Finding | None = None
    clauses: dict[str, Finding] = {}
    evidence: tuple[EvidenceSpan, ...] = ()
    requested_model: str = "typesafe/jev-1.13"
    returned_model: str | None = None
    question_version: str = "counterparts-v1"
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    limitations: tuple[str, ...] = ()
    error: str | None = None
    recorded: bool = False
    supports_candidate: bool = False


class ClassificationRun(AdviceModel):
    id: str
    match_id: str
    mode: str
    input_hash: str
    request: dict
    summary: ClassificationSummary
    response: dict | None = None
    usage: dict = {}
    attempts: int
    applied: bool
    semantic_inputs: dict = {}
