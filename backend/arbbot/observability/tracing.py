"""Opt-in, process-owned tracing. No global provider or automatic payload capture."""

import logging
from contextlib import contextmanager

import requests
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger(__name__)


class ExportLogRedaction(logging.Filter):
    """The OTLP exporter can log server-controlled reasons and transport errors."""

    def filter(self, record):
        record.msg, record.args = "tracing_export_diagnostic", ()
        record.exc_info = record.exc_text = record.stack_info = None
        return True


class CollectorSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def request(self, *args, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(*args, **kwargs)


class SafeExporter(SpanExporter):
    def __init__(self, exporter):
        self.exporter = exporter

    def export(self, spans):
        try:
            return self.exporter.export(spans)
        except Exception:
            # Never attach the exception, endpoint, headers, or collector response.
            logger.warning("tracing_export_failed")
            return SpanExportResult.FAILURE

    def shutdown(self):
        try:
            self.exporter.shutdown()
        except Exception:
            logger.warning("tracing_shutdown_failed")


class Tracing:
    def __init__(self, provider=None):
        self.provider = provider
        self.tracer = provider.get_tracer("arbbot", "0.1.0") if provider else None

    @contextmanager
    def span(self, name, *, root=False, kind=SpanKind.INTERNAL, **attributes):
        if self.tracer is None:
            yield trace.INVALID_SPAN
            return
        with self.tracer.start_as_current_span(
            name,
            context=Context() if root else None,
            kind=kind,
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield span
            except BaseException:
                span.set_status(Status(StatusCode.ERROR))
                raise

    def shutdown(self):
        if self.provider:
            self.provider.shutdown()


def create_tracing(settings, service, *, exporter=None):
    if not settings.tracing_enabled:
        return Tracing()
    try:
        if exporter is None:
            export_logger = logging.getLogger(OTLPSpanExporter.__module__)
            if not any(isinstance(f, ExportLogRedaction) for f in export_logger.filters):
                export_logger.addFilter(ExportLogRedaction())
            exporter = OTLPSpanExporter(
                endpoint=settings.tracing_endpoint,
                headers={
                    "User-Agent": "arbbot-telemetry",
                    **{k: v.get_secret_value() for k, v in settings.tracing_headers.items()},
                },
                timeout=settings.tracing_export_timeout_seconds,
                compression=Compression.NoCompression,
                session=CollectorSession(),
            )
        provider = TracerProvider(
            resource=Resource({"service.name": service, "arbbot.mode": settings.mode}),
            sampler=ParentBased(TraceIdRatioBased(settings.tracing_sample_ratio)),
            span_limits=SpanLimits(
                max_attributes=16, max_attribute_length=128, max_events=0, max_links=0
            ),
            shutdown_on_exit=False,
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                SafeExporter(exporter),
                max_queue_size=settings.tracing_queue_size,
                max_export_batch_size=64,
                schedule_delay_millis=1000,
                export_timeout_millis=int(settings.tracing_export_timeout_seconds * 1000),
            )
        )
        return Tracing(provider)
    except Exception:
        logger.warning("tracing_initialization_failed")
        return Tracing()


def correlation_fields():
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {"trace_id": f"{context.trace_id:032x}", "span_id": f"{context.span_id:016x}"}
