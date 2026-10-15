from pydantic import AwareDatetime

from arbbot.domain import Model, SettlementModel
from arbbot.matching.contracts import Comparison, ContractDefinition
from arbbot.qualification.summary import QualificationSummary


class ContractEvidence(Model):
    definition: ContractDefinition
    artifact_ids: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    expires_at: AwareDatetime
    provider_version: str


class Assessment(Model):
    id: str
    match_id: str
    mode: str
    pair: tuple[str, str]
    input_hash: str
    summary: QualificationSummary
    comparison: Comparison | None = None
    settlement: SettlementModel | None = None
    started_at: AwareDatetime
    inputs: dict
