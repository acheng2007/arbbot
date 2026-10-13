import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from opentelemetry.trace import SpanKind, Status, StatusCode
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from arbbot.api.routes.catalog import catalog_router
from arbbot.api.routes.reviews import reviews_router
from arbbot.api.routes.sources import sources_router
from arbbot.auth.dependencies import require_viewer
from arbbot.auth.service import Authenticator, Principal
from arbbot.config import Settings
from arbbot.discovery.models import CatalogReport
from arbbot.discovery.service import catalog_reports
from arbbot.domain import Book, Evaluation, Market, Opportunity, OpportunityState, utcnow
from arbbot.matching.extraction import Extraction, extract_contract
from arbbot.observability.tracing import Tracing, correlation_fields, create_tracing
from arbbot.storage.database import Database
from arbbot.storage.repository import Repository
from arbbot.venues import VenueInfo, venue_info

PageSize = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=100000)]


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
    tracing: Tracing | None = None,
) -> FastAPI:
    settings = settings or Settings()
    db = database or Database(settings)
    repository = Repository(db, allow_file_reviews=settings.review_source == "files")
    authenticator = Authenticator(settings)
    registry = CollectorRegistry()
    requests = Counter(
        "arbbot_http_requests_total", "HTTP responses", ["route", "status"], registry=registry
    )
    latency = Histogram(
        "arbbot_http_seconds", "HTTP response start latency", ["route"], registry=registry
    )

    @asynccontextmanager
    async def lifespan(app):
        app.state.tracing = tracing or create_tracing(settings, "arbbot-api")
        try:
            yield
        finally:
            try:
                try:
                    await authenticator.close()
                finally:
                    if database is None:
                        await db.close()
            finally:
                if tracing is None:
                    await asyncio.to_thread(app.state.tracing.shutdown)

    app = FastAPI(
        title="Arbbot API",
        version="0.1.0",
        lifespan=lifespan,
        description="Market discovery and authenticated settlement review API. "
        "Simulation data is explicitly labeled. "
        "Live opportunities are conditional estimates, not execution guarantees.",
    )
    app.state.repository = repository
    app.state.authenticator = authenticator
    app.state.auth_origins = frozenset(settings.cors_origins)
    app.state.tracing = tracing or Tracing()
    app.include_router(
        catalog_router(
            db,
            settings.mode,
            allow_file_reviews=settings.review_source == "files",
            venues=settings.enabled_venues,
        )
    )
    app.include_router(sources_router(db, settings.mode))
    app.include_router(reviews_router(db, settings.mode))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept", "Last-Event-ID", "Authorization", "Content-Type", "If-Match"],
    )

    @app.middleware("http")
    async def metrics(request, call_next):
        start = time.monotonic()
        with app.state.tracing.span("api.request", root=True, kind=SpanKind.SERVER) as span:
            method = (
                request.method
                if request.method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
                else "OTHER"
            )
            span.set_attribute("http.request.method", method)
            response = await call_next(request)
            route = getattr(request.scope.get("route"), "path", "unmatched")
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            correlation = correlation_fields()
            if correlation:
                response.headers["X-Arbbot-Trace-Id"] = correlation["trace_id"]
        route = getattr(request.scope.get("route"), "path", "unmatched")
        requests.labels(route, str(response.status_code)).inc()
        latency.labels(route).observe(time.monotonic() - start)
        response.headers["X-Arbbot-Mode"] = settings.mode
        return response

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(request, exc):
        return JSONResponse(
            status_code=503, content={"detail": "Database unavailable or migrations pending"}
        )

    @app.get("/health/live")
    async def liveness():
        return {"status": "ok", "mode": settings.mode}

    @app.get("/api/v1/auth/me", response_model=Principal)
    async def identity(principal: Annotated[Principal, Depends(require_viewer)]):
        return principal

    @app.get("/health/ready")
    async def readiness():
        async with db.sessions() as session:
            await session.execute(text("SELECT 1 FROM markets LIMIT 1"))
        return {"status": "ready", "mode": settings.mode}

    @app.get("/metrics", include_in_schema=False)
    async def prometheus():
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    @app.get("/api/v1/venues", response_model=list[VenueInfo])
    async def venues():
        return venue_info(settings)

    @app.get("/api/v1/status")
    async def status():
        health = await repository.health(settings.mode, settings.health_timeout_seconds)
        health = [h for h in health if h["venue"] in settings.enabled_venues]
        return {
            "mode": settings.mode,
            "exchanges": health,
            "ingestion_healthy": len(health) == len(settings.enabled_venues)
            and all(h["status"] == "healthy" for h in health),
            "discovery_limit_per_exchange": settings.discovery_limit,
            "monitoring_limit_per_exchange": {
                v: settings.monitoring_limit(v) for v in settings.enabled_venues
            },
            "feed_origin": "recorded_exchange" if settings.recording_file else "exchange",
            "ingestion_transport": (
                "Kalshi REST; Polymarket WebSocket book + price_change"
                if settings.mode == "live"
                and settings.polymarket_websocket
                and "polymarket" in settings.enabled_venues
                else "REST full snapshots"
            ),
            "max_quote_age_seconds": settings.max_quote_age_seconds,
        }

    @app.get("/api/v1/discovery", response_model=list[CatalogReport])
    async def discovery():
        return await catalog_reports(db, settings.mode)

    @app.get("/api/v1/markets/{market_id}", response_model=Market)
    async def market(market_id: str):
        result = await repository.market(settings.mode, market_id)
        if result is None:
            raise HTTPException(404, "Market not found")
        return result

    @app.get("/api/v1/markets/{market_id}/extraction", response_model=Extraction)
    async def extraction(market_id: str):
        result = await repository.market(settings.mode, market_id)
        if result is None:
            raise HTTPException(404, "Market not found")
        return extract_contract(result)

    @app.get("/api/v1/markets/{market_id}/book", response_model=Book)
    async def book(market_id: str):
        result = await repository.book(settings.mode, market_id)
        if result is None:
            raise HTTPException(404, "Order book not available")
        return result

    @app.get("/api/v1/markets/{market_id}/versions/{terms_hash}", response_model=Market)
    async def market_version(market_id: str, terms_hash: str):
        result = await repository.market_version(settings.mode, market_id, terms_hash)
        if result is None:
            raise HTTPException(404, "Market version not found")
        return result

    @app.get("/api/v1/snapshots/{snapshot_id}", response_model=Book)
    async def snapshot(snapshot_id: str):
        result = await repository.snapshot(settings.mode, snapshot_id)
        if result is None:
            raise HTTPException(404, "Snapshot not found")
        return result

    @app.get("/api/v1/opportunities", response_model=list[Opportunity])
    async def opportunities(limit: PageSize = 100, offset: Offset = 0):
        return await repository.opportunities(
            settings.mode,
            settings.health_timeout_seconds,
            limit,
            offset,
            enabled_venues=settings.enabled_venues,
        )

    @app.get("/api/v1/opportunities/history", response_model=list[Opportunity])
    async def history(limit: PageSize = 100, offset: Offset = 0):
        return await repository.opportunities(
            settings.mode, settings.health_timeout_seconds, limit, offset, history=True
        )

    @app.get("/api/v1/opportunities/{opportunity_id}", response_model=OpportunityState)
    async def opportunity(opportunity_id: str):
        historical = await repository.opportunities(
            settings.mode,
            settings.health_timeout_seconds,
            history=True,
            opportunity_id=opportunity_id,
        )
        if not historical:
            raise HTTPException(404, "Opportunity not found")
        current = await repository.opportunities(
            settings.mode,
            settings.health_timeout_seconds,
            enabled_venues=settings.enabled_venues,
            opportunity_id=opportunity_id,
        )
        from arbbot.execution.invalidation import invalidation_reasons

        reasons = () if current else await invalidation_reasons(repository, settings, historical[0])
        return OpportunityState(
            opportunity=historical[0], eligible=bool(current), invalidation_reasons=reasons
        )

    @app.get("/api/v1/evaluations", response_model=list[Evaluation])
    async def evaluations(
        limit: PageSize = 100,
        offset: Offset = 0,
        history: bool = False,
        match_id: str | None = None,
        status: Literal["profitable", "unprofitable", "blocked", "invalid"] | None = None,
    ):
        return await repository.evaluations(
            settings.mode, limit, offset, history=history, match_id=match_id, status=status
        )

    @app.get("/api/v1/stream", response_class=StreamingResponse)
    async def stream(request: Request):
        async def events():
            # Each event is a full current view. Reconnection does not require replay.
            while not await request.is_disconnected():
                rows = await repository.opportunities(
                    settings.mode,
                    settings.health_timeout_seconds,
                    limit=200,
                    enabled_venues=settings.enabled_venues,
                )
                health = await repository.health(settings.mode, settings.health_timeout_seconds)
                health = [h for h in health if h["venue"] in settings.enabled_venues]
                payload = {
                    "mode": settings.mode,
                    "as_of": utcnow().isoformat(),
                    "opportunities": [row.model_dump(mode="json") for row in rows],
                    "exchanges": health,
                    "limit": 200,
                }
                yield "event: snapshot\ndata: " + json.dumps(payload) + "\n\n"
                await asyncio.sleep(settings.sse_seconds)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
