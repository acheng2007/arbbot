from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from arbbot.domain import Book, Mode, Model, NonNegative, Outcome, Probability

Sequence = Annotated[StrictInt, Field(ge=0, le=2**63 - 1)]
Epoch = Annotated[str, Field(min_length=1, max_length=128)]


class Snapshot(Model):
    kind: Literal["snapshot"] = "snapshot"
    epoch: Epoch
    sequence: Sequence
    book: Book


class LevelChange(Model):
    outcome: Outcome
    price: Probability
    # Absolute replacement quantity; zero deletes a level. Adapters normalize wire deltas.
    size: NonNegative


class Delta(Model):
    kind: Literal["delta"] = "delta"
    epoch: Epoch
    sequence: Sequence
    previous_sequence: Sequence
    market_id: str = Field(min_length=1)
    mode: Mode
    source_at: AwareDatetime | None
    received_at: AwareDatetime
    changes: tuple[LevelChange, ...] = Field(min_length=1, max_length=10000)
    raw: dict

    @model_validator(mode="after")
    def validate_changes(self):
        if self.previous_sequence >= self.sequence:
            raise ValueError("A delta must advance its predecessor sequence")
        if len({(c.outcome, c.price) for c in self.changes}) != len(self.changes):
            raise ValueError("Duplicate level replacements must be normalized by the adapter")
        return self


class Disconnected(Model):
    kind: Literal["disconnected"] = "disconnected"
    epoch: Epoch
    reason: Literal["transport_error", "closed", "heartbeat_timeout", "integrity_failure"]


StreamEvent = Annotated[Snapshot | Delta | Disconnected, Field(discriminator="kind")]
