from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Document = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class MarketRecord(Base):
    __tablename__ = "markets"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    id: Mapped[str] = mapped_column(String, index=True)
    mode: Mapped[str] = mapped_column(String, index=True)
    venue: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(Document)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latest_book_id: Mapped[str | None] = mapped_column(String, nullable=True)


class SnapshotRecord(Base):
    __tablename__ = "book_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_key: Mapped[str] = mapped_column(ForeignKey("markets.key"), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(Document)


class MarketVersionRecord(Base):
    __tablename__ = "market_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_key: Mapped[str] = mapped_column(ForeignKey("markets.key"), index=True)
    terms_hash: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(Document)


class MatchRecord(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String, index=True)
    current: Mapped[bool] = mapped_column(Boolean, index=True)
    payload: Mapped[dict] = mapped_column(Document)


class EvaluationRecord(Base):
    __tablename__ = "evaluations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    mode: Mapped[str] = mapped_column(String, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(Document)


class OpportunityRecord(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    mode: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    net_profit: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    capital_required: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    payload: Mapped[dict] = mapped_column(Document)
    __table_args__ = (Index("ix_opportunity_feed", "mode", "active", "valid_until"),)


class HealthRecord(Base):
    __tablename__ = "exchange_health"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String, index=True)
    venue: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(Document)


class SourceArtifactRecord(Base):
    __tablename__ = "source_artifacts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_key: Mapped[str] = mapped_column(ForeignKey("markets.key"), index=True)
    venue: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String(255))
    content_digest: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    __table_args__ = (
        CheckConstraint("length(content) > 0 AND length(content) <= 2097152", name="source_size"),
    )


class SourceCaptureRecord(Base):
    __tablename__ = "source_captures"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_key: Mapped[str] = mapped_column(ForeignKey("markets.key"), index=True)
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("source_artifacts.id"))
    venue: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_type: Mapped[str | None] = mapped_column(String(255))
    failure: Mapped[str | None] = mapped_column(String)
    http_status: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint(
            "(artifact_id IS NOT NULL AND failure IS NULL) OR "
            "(artifact_id IS NULL AND failure IS NOT NULL)",
            name="source_result",
        ),
    )
