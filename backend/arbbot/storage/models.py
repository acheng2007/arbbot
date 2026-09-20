from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Numeric, String, false
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
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    __table_args__ = (Index("ix_market_family_page", "mode", "family", "id"),)


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
    evidence_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


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
