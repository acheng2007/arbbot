from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict

QualificationStatus = Literal[
    "pending", "qualified", "incomplete", "incompatible", "stale", "unavailable"
]


class QualificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: QualificationStatus = "pending"
    basis: Literal["automatic_rules"] = "automatic_rules"
    assessment_id: str | None = None
    input_hash: str | None = None
    policy_version: str | None = None
    completed_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    blocked_reasons: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
