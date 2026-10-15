from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints, computed_field, model_validator

from arbbot.domain import Market, Mode, Model, Review, digest
from arbbot.matching.contracts import ContractDefinition

RevisionId = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)]


class Actor(Model):
    """Server-derived identity. Never accept this object from a mutation body."""

    issuer: str = Field(min_length=1, max_length=2048)
    subject: str = Field(min_length=1, max_length=512)

    @computed_field
    @property
    def audit_id(self) -> str:
        return digest([self.issuer, self.subject])


class DraftWrite(Model):
    expected_revision_id: RevisionId | None = None
    definition: ContractDefinition
    source_artifact_ids: tuple[Hash, ...] = Field(default=(), max_length=64)
    reason: Reason

    @model_validator(mode="after")
    def unique_sources(self):
        if len(set(self.source_artifact_ids)) != len(self.source_artifact_ids):
            raise ValueError("Source artifact references must be unique")
        return self


class DraftRevision(Model):
    source_revisions: dict[str, int] | None = None
    source_revision: int = Field(default=0, ge=0)
    id: RevisionId
    previous_revision_id: RevisionId | None
    revision: int = Field(ge=1)
    market: Market
    definition: ContractDefinition
    definition_hash: Hash
    source_artifact_ids: tuple[Hash, ...]
    actor: Actor
    created_at: AwareDatetime
    reason: Reason


class DecisionWrite(Model):
    expected_revision_id: RevisionId | None = None
    left_draft_id: RevisionId
    right_draft_id: RevisionId
    action: Literal["verified", "rejected", "revoked", "cleared"]
    reason: Reason
    review: Review | None = None

    @model_validator(mode="after")
    def action_payload(self):
        if self.action == "verified" and (self.review is None or self.review.status != "verified"):
            raise ValueError("Verification requires a complete approval payload")
        if self.action != "verified" and self.review is not None:
            raise ValueError("Non-approval actions use a reason, not an approval payload")
        if self.left_draft_id == self.right_draft_id:
            raise ValueError("A decision must bind two different drafts")
        return self


class DecisionRevision(Model):
    applicability_revision_ids: tuple[str, ...] = ()
    id: RevisionId
    previous_revision_id: RevisionId | None
    revision: int = Field(ge=1)
    mode: Mode
    pair_key: Hash
    left_id: str
    right_id: str
    left_draft_id: RevisionId
    right_draft_id: RevisionId
    action: Literal["verified", "rejected", "revoked", "cleared"]
    reason: Reason
    review: Review | None
    actor: Actor
    created_at: AwareDatetime


class DecisionState(Model):
    revision: DecisionRevision
    eligible: bool
    blocked_reasons: tuple[str, ...]


class RevisionConflict(Exception):
    def __init__(self, message, current_revision_id=None, *, issues=()):
        super().__init__(message)
        self.current_revision_id = current_revision_id
        self.issues = tuple(issues)


class ReviewValidationError(ValueError):
    def __init__(self, issues):
        super().__init__("Review evidence is invalid or incomplete")
        self.issues = tuple(issues)


def pair_key(mode, left_id, right_id):
    return digest([mode, *sorted((left_id, right_id))])


def payload(value):
    # Nested markets and actors have computed output fields. Recompute them from
    # their saved inputs on read, rather than accepting stored computed values.
    return value.model_dump(mode="json", exclude_computed_fields=True)
