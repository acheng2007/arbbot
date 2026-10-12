from datetime import timedelta
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, StrictBool, field_validator, model_validator

from arbbot.domain import Model, Venue
from arbbot.reviews.models import Actor, Hash, RevisionId


class Citation(Model):
    artifact_id: Hash
    content_hash: Hash
    quotation: str = Field(min_length=10, max_length=8000)


class Permission(Model):
    venue: Venue
    market_ids: tuple[str, ...] = Field(min_length=1, max_length=10000)
    short_allowed: StrictBool
    fee_account_class: Literal["direct", "non_direct", "standard"]

    @model_validator(mode="after")
    def identity(self):
        if any(not mid.startswith(self.venue + ":") for mid in self.market_ids):
            raise ValueError("Permission market identities must belong to the venue")
        return self


class AccessProfile(Model):
    kind: Literal["access"] = "access"
    jurisdiction: str = Field(min_length=2, max_length=100)
    status: Literal["verified", "restricted", "unknown"]
    permissions: tuple[Permission, ...] = Field(min_length=1, max_length=3)
    supporting_evidence: tuple[str, ...] = Field(min_length=1, max_length=32)
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def unique_venues(self):
        if len({p.venue for p in self.permissions}) != len(self.permissions):
            raise ValueError("Only one permission entry per venue")
        return self


class Applicability(Model):
    kind: Literal["applicability"] = "applicability"
    market_id: str = Field(min_length=1, max_length=512)
    terms_hash: Hash
    product_id: str = Field(min_length=1, max_length=512)
    status: Literal["verified", "revoked"]
    specifications: tuple[Citation, ...] = Field(min_length=1, max_length=32)
    amendments: tuple[Citation, ...] = Field(default=(), max_length=64)
    amendment_inventory: Citation
    rationale: str = Field(min_length=20, max_length=8000)
    expires_at: AwareDatetime


class ExecutableFeePolicy(Model):
    kind: Literal["fees"] = "fees"
    market_id: str = Field(min_length=1, max_length=512)
    venue: Literal["kalshi", "polymarket_us"]
    terms_hash: Hash
    formula: Literal["kalshi_quadratic", "us_standard"]
    coefficient: Decimal = Field(ge=0, le=7, allow_inf_nan=False)
    minimum_execution_quantity: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    balance_precision: Literal["0.0001", "0.01"] | None = None
    account_class: Literal["direct", "non_direct", "standard"]
    source: Citation
    supporting_sources: tuple[Citation, ...] = Field(default=(), max_length=16)
    metadata_hash: Hash
    metadata: dict = {}
    observed_at: AwareDatetime
    effective_at: AwareDatetime
    expires_at: AwareDatetime

    @field_validator("coefficient", "minimum_execution_quantity", mode="before")
    @classmethod
    def exact_money(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Financial policy values require exact decimal inputs")
        return value

    @model_validator(mode="after")
    def supported_policy(self):
        if not self.market_id.startswith(self.venue + ":"):
            raise ValueError("Fee identities must belong to venue")
        if (
            self.effective_at >= self.expires_at
            or self.observed_at >= self.expires_at
            or self.expires_at > self.observed_at + timedelta(minutes=15)
        ):
            raise ValueError("Fee policy lifetime is invalid")
        if (self.venue == "kalshi") != (self.formula == "kalshi_quadratic"):
            raise ValueError("Fee formula does not belong to venue")
        if self.formula == "kalshi_quadratic" and (
            self.account_class not in ("direct", "non_direct")
            or self.balance_precision != ("0.0001" if self.account_class == "direct" else "0.01")
            or self.minimum_execution_quantity not in (None, Decimal("0.01"))
        ):
            raise ValueError("Unverified Kalshi account precision or execution granularity")
        if self.formula == "us_standard" and (
            self.coefficient not in (Decimal("0.0695"), Decimal("0.10"))
            or self.account_class != "standard"
        ):
            raise ValueError("Only documented standard US policies are supported")
        return self


class UnavailableFeePolicy(Model):
    kind: Literal["fee_unavailable"] = "fee_unavailable"
    market_id: str = Field(min_length=1, max_length=512)
    terms_hash: Hash
    reason: Literal[
        "provider_error",
        "unsupported_policy",
        "incomplete_metadata",
        "stale",
        "unverified_account_fees",
    ]
    expires_at: AwareDatetime


Configuration = AccessProfile | Applicability | ExecutableFeePolicy | UnavailableFeePolicy


class ConfigurationWrite(Model):
    expected_revision_id: RevisionId | None = None
    value: Configuration = Field(discriminator="kind")
    reason: str = Field(min_length=10, max_length=4000)


class ConfigurationRevision(Model):
    id: RevisionId
    previous_revision_id: RevisionId | None
    mode: Literal["live", "simulation"]
    key: str
    value: Configuration = Field(discriminator="kind")
    actor: Actor
    created_at: AwareDatetime
    reason: str


class ExecutionContext(Model):
    access_revision_id: str | None = None
    applicability_revision_ids: tuple[str, ...] = ()
    fee_revision_ids: tuple[str, ...] = ()
    policies: tuple[ExecutableFeePolicy, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    valid_until: AwareDatetime | None = None
    short_allowed_market_ids: tuple[str, ...] = ()


class AccessSummary(Model):
    status: Literal["unknown", "verified", "restricted", "expired"]
    revision_id: str | None = None
    permitted_venues: tuple[Venue, ...] = ()
    expires_at: AwareDatetime | None = None
