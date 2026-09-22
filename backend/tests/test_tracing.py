import asyncio
import json
import logging
import threading

import httpx
import pytest
import requests
from opentelemetry import trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from pydantic import ValidationError

from arbbot.api.app import create_app
from arbbot.config import Settings
from arbbot.exchanges.simulation import SimulationAdapter
from arbbot.ingestion.pipeline import Pipeline
from arbbot.observability.tracing import CollectorSession, create_tracing
from arbbot.workers.main import JSONFormatter


def configured(settings=None, **updates):
    settings = settings or Settings(_env_file=None)
    return settings.model_copy(
        update={"tracing_enabled": True, "tracing_sample_ratio": 1, **updates}
    )


async def flush(tracing):
    assert await asyncio.to_thread(tracing.provider.force_flush, 3000)


async def test_pipeline_to_api_spans_and_concurrent_context(database):
    settings, db, repository = database
    exporter = InMemorySpanExporter()
    original_provider = trace.get_tracer_provider()
    tracing = create_tracing(configured(settings), "test", exporter=exporter)
    try:
        adapters = [SimulationAdapter(venue) for venue in ("kalshi", "polymarket")]
        result = await Pipeline(settings, repository, adapters, tracing=tracing).cycle()
        assert result["opportunities"] > 0
        app = create_app(settings, db, tracing=tracing)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as c:
            response = await c.get(
                "/api/v1/opportunities?secret=PRIVATE",
                headers={
                    "authorization": "Bearer PRIVATE",
                    "traceparent": "00-11111111111111111111111111111111-1111111111111111-01",
                    "baggage": "password=PRIVATE",
                },
            )
            assert response.status_code == 200
            assert response.json()
        await flush(tracing)
        spans = exporter.get_finished_spans()
        cycle = next(s for s in spans if s.name == "ingestion.cycle")
        api = next(s for s in spans if s.name == "api.request")
        assert api.parent is None and cycle.parent is None
        assert api.context.trace_id != cycle.context.trace_id
        assert api.context.trace_id != int("1" * 32, 16)
        assert response.headers["x-arbbot-trace-id"] == f"{api.context.trace_id:032x}"
        assert api.attributes["http.route"] == "/api/v1/opportunities"
        children = [s for s in spans if s not in (cycle, api)]
        assert {s.name for s in children} == {
            "ingestion.catalog",
            "ingestion.book",
            "matching",
            "evaluation",
            "publication",
        }
        for child in children:
            assert child.parent.span_id == cycle.context.span_id
            assert child.context.trace_id == cycle.context.trace_id
        assert len([s for s in children if s.name == "ingestion.book"]) == 2
        assert "PRIVATE" not in "".join(s.to_json() for s in spans)
        assert trace.get_tracer_provider() is original_provider
        assert not trace.get_current_span().get_span_context().is_valid
    finally:
        await asyncio.to_thread(tracing.shutdown)


async def test_disabled_and_zero_sampling_preserve_behavior(database):
    settings, db, repository = database
    for enabled in (False, True):
        exporter = InMemorySpanExporter()
        tracing = create_tracing(
            configured(settings, tracing_enabled=enabled, tracing_sample_ratio=0),
            "test",
            exporter=exporter,
        )
        try:
            result = await Pipeline(
                settings,
                repository,
                [SimulationAdapter(v) for v in ("kalshi", "polymarket")],
                tracing=tracing,
            ).cycle()
            assert result["opportunities"] > 0
            if enabled:
                await flush(tracing)
            else:
                assert tracing.provider is None
            assert not exporter.get_finished_spans()
        finally:
            await asyncio.to_thread(tracing.shutdown)


async def test_error_and_request_redaction(database):
    settings, db, _ = database
    exporter = InMemorySpanExporter()
    tracing = create_tracing(configured(settings), "test", exporter=exporter)
    app = create_app(settings, db, tracing=tracing)

    @app.get("/test/error")
    async def fail():
        raise RuntimeError("PRIVATE_DATABASE_CREDENTIALS")

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, raise_app_exceptions=False), base_url="http://test"
        ) as c:
            assert (await c.get("/test/error")).status_code == 500
            assert (await c.get("/api/v1/markets/PRIVATE_SOURCE_ID")).status_code == 404
            assert (await c.get("/PRIVATE_PATH?secret=PRIVATE_QUERY")).status_code == 404
        with tracing.span("logging", root=True):
            record = logging.LogRecord("test", logging.INFO, "", 1, "cycle", (), None)
            fields = json.loads(JSONFormatter().format(record))
            assert len(fields["trace_id"]) == 32 and len(fields["span_id"]) == 16
        await flush(tracing)
        spans = exporter.get_finished_spans()
        assert any(s.status.status_code == StatusCode.ERROR for s in spans)
        assert all(not s.events and s.status.description is None for s in spans)
        assert "PRIVATE" not in "".join(s.to_json() for s in spans)
    finally:
        await asyncio.to_thread(tracing.shutdown)


async def test_failing_exporter_cannot_interrupt_discovery(database, caplog):
    class Broken(SpanExporter):
        def export(self, spans):
            raise RuntimeError("PRIVATE_EXPORT_TOKEN")

        def shutdown(self):
            raise RuntimeError("PRIVATE_SHUTDOWN_TOKEN")

    settings, _, repository = database
    tracing = create_tracing(configured(settings), "test", exporter=Broken())
    try:
        result = await Pipeline(
            settings,
            repository,
            [SimulationAdapter(v) for v in ("kalshi", "polymarket")],
            tracing=tracing,
        ).cycle()
        assert result["opportunities"] > 0
        await flush(tracing)
        assert "tracing_export_failed" in caplog.text
    finally:
        await asyncio.to_thread(tracing.shutdown)
    assert "tracing_shutdown_failed" in caplog.text
    assert "PRIVATE" not in caplog.text


async def test_export_queue_does_not_block_event_loop():
    entered, release = threading.Event(), threading.Event()

    class Slow(SpanExporter):
        def export(self, spans):
            entered.set()
            release.wait(5)
            return SpanExportResult.SUCCESS

    tracing = create_tracing(configured(tracing_queue_size=64), "test", exporter=Slow())
    try:
        for _ in range(64):
            with tracing.span("queued", root=True):
                pass
        assert await asyncio.to_thread(entered.wait, 2)
        for _ in range(256):
            with tracing.span("queue_overflow", root=True):
                await asyncio.sleep(0)
        assert not release.is_set()
    finally:
        release.set()
        await asyncio.to_thread(tracing.shutdown)


async def test_collector_logs_are_redacted_and_redirects_disabled(monkeypatch, caplog):
    calls = []

    def reject(self, *args, **kwargs):
        calls.append(kwargs)
        response = requests.Response()
        response.status_code = 401
        response.reason = "PRIVATE_COLLECTOR_RESPONSE"
        return response

    monkeypatch.setattr(requests.Session, "request", reject)
    tracing = create_tracing(configured(), "test")
    try:
        with tracing.span("test", root=True):
            pass
        await flush(tracing)
        assert calls and calls[0]["allow_redirects"] is False
        payload = ExportTraceServiceRequest.FromString(calls[0]["data"])
        assert payload.resource_spans[0].scope_spans[0].spans[0].name == "test"
        assert calls[0]["timeout"] <= 2
        assert "tracing_export_diagnostic" in caplog.text
        assert "PRIVATE" not in caplog.text
        assert CollectorSession().trust_env is False
    finally:
        await asyncio.to_thread(tracing.shutdown)


@pytest.mark.parametrize(
    "endpoint", ["http://remote/traces", "https://user:pass@host/traces", "https://host/?secret=1"]
)
def test_endpoint_rejects_credentials_and_remote_plaintext(endpoint):
    with pytest.raises(ValidationError):
        Settings(tracing_endpoint=endpoint, _env_file=None)


async def test_api_lifespan_owns_provider(database, monkeypatch):
    settings, db, _ = database
    exporter = InMemorySpanExporter()
    tracing = create_tracing(configured(settings), "test", exporter=exporter)
    monkeypatch.setattr("arbbot.api.app.create_tracing", lambda *args: tracing)
    app = create_app(settings, db)
    assert app.state.tracing.provider is None
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as c:
            assert (await c.get("/health/live")).status_code == 200
    assert len(exporter.get_finished_spans()) == 1


def test_initialization_failure_and_disabled_mode(monkeypatch, caplog):
    def broken(**kwargs):
        raise RuntimeError("PRIVATE_CONFIGURATION")

    monkeypatch.setattr("arbbot.observability.tracing.OTLPSpanExporter", broken)
    assert create_tracing(Settings(_env_file=None), "test").provider is None
    assert not caplog.records
    assert create_tracing(configured(), "test").provider is None
    assert "tracing_initialization_failed" in caplog.text
    assert "PRIVATE" not in caplog.text


async def test_tracing_cleanup_survives_authenticator_close_failure(database, monkeypatch):
    settings, db, _ = database
    exporter = InMemorySpanExporter()
    tracing = create_tracing(configured(settings), "test", exporter=exporter)
    monkeypatch.setattr("arbbot.api.app.create_tracing", lambda *args: tracing)
    app = create_app(settings, db)

    async def fail_close():
        raise RuntimeError("authenticator shutdown failed")

    monkeypatch.setattr(app.state.authenticator, "close", fail_close)
    with pytest.raises(RuntimeError, match="authenticator shutdown failed"):
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/auth/me")
                assert response.status_code == 401
                assert "x-arbbot-trace-id" in response.headers
    # Provider shutdown flushes the pending request even when another resource fails.
    assert len(exporter.get_finished_spans()) == 1
