from decimal import Decimal
from uuid import uuid4

from sqlalchemy import update

from arbbot.domain import utcnow
from arbbot.execution.models import (
    AccessProfile,
    Applicability,
    ConfigurationRevision,
    ExecutionContext,
)
from arbbot.reviews.models import ReviewValidationError, RevisionConflict, payload
from arbbot.reviews.repository import ReviewRepository
from arbbot.sources.text import derive_text
from arbbot.storage.models import (
    ConfigurationHeadRecord,
    ConfigurationRevisionRecord,
    OpportunityRecord,
)


def configuration_key(mode, value):
    return f"{mode}:{value.kind}:" + ("installation" if value.kind == "access" else value.market_id)


class ExecutionRepository:
    def __init__(self, database):
        self.database = database
        self.reviews = ReviewRepository(database)

    async def current(self, session, key, *, lock=False):
        head = await session.get(ConfigurationHeadRecord, key, with_for_update=lock)
        if not head:
            return None
        row = await session.get(ConfigurationRevisionRecord, head.revision_id)
        return ConfigurationRevision.model_validate(row.payload)

    async def save(self, mode, request, actor):
        key = configuration_key(mode, request.value)
        derived = {}
        value = request.value
        if value.kind != "access":
            from arbbot.sources.repository import SourceRepository

            citations = (
                (value.source,)
                if value.kind == "fees"
                else (*value.specifications, *value.amendments, value.amendment_inventory)
            )
            for citation in citations:
                source = await SourceRepository(self.database).get(mode, citation.artifact_id)
                if source and source.content:
                    text = await derive_text(source.content, source.content_type, source.id)
                    derived[citation.artifact_id] = text
        async with self.reviews._write() as session:
            # Serialize through market rows just like draft/source mutations.
            value = request.value
            if value.kind != "access":
                market = await self.reviews._market(session, mode, value.market_id, lock=True)
                if market.terms_hash != value.terms_hash:
                    raise ReviewValidationError(("configuration_terms_changed",))
                citations = (
                    (value.source,)
                    if value.kind == "fees"
                    else (*value.specifications, *value.amendments, value.amendment_inventory)
                )
                issues = await self.reviews._source_issues(
                    session, market, tuple(c.artifact_id for c in citations)
                )
                from arbbot.sources.repository import artifact
                from arbbot.storage.models import SourceArtifactRecord

                for citation in citations:
                    row = await session.get(SourceArtifactRecord, citation.artifact_id)
                    if not row:
                        continue
                    source = artifact(row)
                    from urllib.parse import urlsplit

                    from arbbot.sources.fetch import ALLOWED_HOSTS

                    if mode == "live" and urlsplit(str(source.url)).hostname not in ALLOWED_HOSTS:
                        issues.append("configuration_source_host_unverified")
                    if source.content_digest != citation.content_hash:
                        issues.append("configuration_source_hash_changed")
                    text = derived.get(citation.artifact_id)
                    if (
                        not text
                        or text.status != "complete"
                        or citation.quotation not in "\n".join(page.text for page in text.pages)
                    ):
                        issues.append("configuration_quotation_not_captured")
                if value.kind == "fees":
                    from arbbot.domain import digest

                    if value.metadata_hash != digest(value.metadata):
                        issues.append("fee_metadata_hash_mismatch")
                    if mode == "live" and value.venue == "kalshi":
                        from arbbot.fees.refresh import kalshi_parameters

                        try:
                            if value.metadata["market"].get("ticker") != market.external_id:
                                issues.append("fee_market_identity_mismatch")
                            coefficient, expiry = kalshi_parameters(
                                value.metadata, value.observed_at
                            )
                            if coefficient != value.coefficient or value.expires_at > expiry:
                                issues.append("fee_metadata_policy_mismatch")
                        except (ValueError, KeyError, TypeError, ArithmeticError):
                            issues.append("fee_metadata_unverified")
                    if mode == "live" and value.venue == "polymarket_us":
                        document = derived.get(value.source.artifact_id)
                        body = "\n".join(p.text for p in document.pages) if document else ""
                        if (
                            str(source.url) != "https://docs.polymarket.us/fees"
                            or not all(
                                x in body
                                for x in (
                                    "October 7, 2026",
                                    "0.0695",
                                    "0.10",
                                    "cumulative exact fee",
                                )
                            )
                            or value.coefficient != Decimal("0.10")
                        ):
                            issues.append("fee_document_policy_unverified")
                if issues:
                    raise ReviewValidationError(tuple(issues))
            if value.expires_at <= utcnow():
                raise ReviewValidationError(("configuration_expired",))
            current = await self.current(session, key, lock=True)
            if (current.id if current else None) != request.expected_revision_id:
                raise RevisionConflict("Configuration changed", current.id if current else None)
            if value.kind == "applicability" and value.status == "verified":
                # Add exact captured text for definition citations. Only reviewed
                # applicability gaps are discharged; unrelated retrieval failures remain.
                details = {
                    k: v
                    for k, v in market.settlement_details.items()
                    if not k.startswith("applicable_document_")
                }
                base_hash = details.get("applicability_base_hash", market.terms_hash)
                for citation in citations:
                    document = derived[citation.artifact_id]
                    details[f"applicable_document_{citation.artifact_id}"] = "\n".join(
                        page.text for page in document.pages
                    )
                details["applicability_base_hash"] = base_hash
                gaps = set(details.get("source_issues", ())) - {
                    "product_specification_applicability_unverified",
                    "clarification_applicability_unverified",
                }
                details["source_issues"] = sorted(gaps)
                details["source_status"] = "incomplete" if gaps else "captured"
                from arbbot.storage.repository import Repository

                market = market.model_copy(update={"settlement_details": details})
                await Repository(self.database).save_market_in_session(session, market)
                value = value.model_copy(update={"terms_hash": market.terms_hash})
            revision = ConfigurationRevision(
                id=uuid4().hex,
                previous_revision_id=current.id if current else None,
                mode=mode,
                key=key,
                value=value,
                actor=actor,
                created_at=utcnow(),
                reason=request.reason,
            )
            session.add(
                ConfigurationRevisionRecord(id=revision.id, key=key, payload=payload(revision))
            )
            await session.flush()
            await session.merge(ConfigurationHeadRecord(key=key, revision_id=revision.id))
            # Withdraw first; publication requires a fresh calculation under the new version.
            query = update(OpportunityRecord).where(OpportunityRecord.mode == mode)
            if value.kind != "access":
                from sqlalchemy import or_

                query = query.where(
                    or_(
                        *(
                            OpportunityRecord.payload["legs"][i]["market_id"].as_string()
                            == value.market_id
                            for i in (0, 1)
                        )
                    )
                )
            await session.execute(query.values(active=False))
            return revision

    async def context(self, session, mode, markets, *, lock=False):
        now, reasons, deadlines = utcnow(), [], []
        access = await self.current(session, f"{mode}:access:installation", lock=lock)
        allowed = {}
        if not access or not isinstance(access.value, AccessProfile):
            reasons.append("installation_access_unknown")
        elif access.value.status != "verified" or access.value.expires_at <= now:
            reasons.append("installation_access_restricted_or_expired")
        else:
            deadlines.append(access.value.expires_at)
            allowed = {p.venue: p for p in access.value.permissions}
        applicability_ids, fee_ids, policies, shorts = [], [], [], []
        for market in markets:
            permission = allowed.get(market.venue)
            if not permission or market.id not in permission.market_ids:
                reasons.append(f"product_access_unverified:{market.id}")
            elif permission.short_allowed:
                shorts.append(market.id)
            app = await self.current(session, f"{mode}:applicability:{market.id}", lock=lock)
            fee = await self.current(session, f"{mode}:fees:{market.id}", lock=lock)
            if (
                not app
                or not isinstance(app.value, Applicability)
                or (
                    app.value.status != "verified"
                    or app.value.terms_hash != market.terms_hash
                    or app.value.expires_at <= now
                )
            ):
                reasons.append(f"source_applicability_unverified:{market.id}")
            else:
                citations = (
                    *app.value.specifications,
                    *app.value.amendments,
                    app.value.amendment_inventory,
                )
                issues = await self.reviews._source_issues(
                    session, market, tuple(c.artifact_id for c in citations)
                )
                reasons.extend(issues)
                applicability_ids.append(app.id)
                deadlines.append(app.value.expires_at)
            if (
                not fee
                or fee.value.kind != "fees"
                or (
                    fee.value.terms_hash != market.terms_hash
                    or fee.value.expires_at <= now
                    or fee.value.effective_at > now
                    or fee.value.observed_at > now
                    or not permission
                    or fee.value.account_class != permission.fee_account_class
                )
            ):
                reasons.append(f"fee_policy_unavailable:{market.id}")
            else:
                reasons.extend(
                    await self.reviews._source_issues(
                        session, market, (fee.value.source.artifact_id,)
                    )
                )
                policies.append(fee.value)
                fee_ids.append(fee.id)
                deadlines.append(fee.value.expires_at)
        return ExecutionContext(
            access_revision_id=access.id if access else None,
            applicability_revision_ids=tuple(applicability_ids),
            fee_revision_ids=tuple(fee_ids),
            policies=tuple(policies),
            blocked_reasons=tuple(reasons),
            valid_until=min(deadlines) if deadlines else None,
            short_allowed_market_ids=tuple(shorts),
        )
