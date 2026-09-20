# Backend tracing

Tracing is disabled by default and does not create an exporter, provider, or background export thread while disabled.
The API and worker each own an OpenTelemetry provider for their process lifetime.
They do not replace the global provider or enable automatic HTTP, SQL, or exception instrumentation.
The implementation pins OpenTelemetry SDK and OTLP/HTTP exporter 1.44.0 with their resolved dependencies in both lockfiles.
See the upstream [Python instrumentation guide](https://opentelemetry.io/docs/languages/python/instrumentation/) and [exporter guide](https://opentelemetry.io/docs/languages/python/exporters/).

## Configuration

Set these variables on each process that should emit traces:

```dotenv
ARBBOT_TRACING_ENABLED=true
ARBBOT_TRACING_ENDPOINT=http://localhost:4318/v1/traces
ARBBOT_TRACING_SAMPLE_RATIO=0.1
ARBBOT_TRACING_EXPORT_TIMEOUT_SECONDS=2
ARBBOT_TRACING_QUEUE_SIZE=512
```

The endpoint is the full OTLP/HTTP traces URL, including `/v1/traces` where required by the collector.
HTTPS is required except for loopback HTTP to a local collector.
In a container, localhost refers to that container; configure an HTTPS collector endpoint reachable from the container if it is hosted separately.
Inject optional `ARBBOT_TRACING_HEADERS` as a JSON object through the deployment secret store.
Header values use Pydantic `SecretStr`; do not put them into committed configuration.
Credentials, query strings, and fragments are not accepted in the endpoint URL.
The exporter disables redirects, ambient HTTP proxies, and netrc credentials.
Arbbot explicitly supplies its endpoint, headers, compression, timeout, resource, and sampler rather than relying on general OpenTelemetry environment defaults for those values.

## Correlation and sampling

Each ingestion cycle starts one root span.
Catalog and book requests, matching, threaded evaluation, and publication are children of that cycle.
Python asynchronous tasks and `asyncio.to_thread` preserve their parent context.
Worker JSON logs emitted inside those operations include trace and span identifiers.

Each API request starts a separate root span and returns `X-Arbbot-Trace-Id` when tracing is enabled.
It records a route template, bounded HTTP method, and status code.
The request span ends when response headers are available, so long-lived SSE connections do not retain an unfinished request span indefinitely.
It does not measure the lifetime or delivery success of an SSE connection.
Public inbound traceparent, tracestate, and baggage are deliberately not accepted as parent context.
Clients cannot force sampling or inject arbitrary telemetry attributes.

The configured ratio samples root traces; children follow their local parent's decision.
Set the ratio to 1 for a controlled diagnostic session or 0 to suppress exports while retaining local trace identifiers.
API reads and worker cycles are separate traces because they communicate through durable database records.
This change does not persist trace identifiers on opportunities or imply cross-process lineage through the database.

## Privacy and failure behavior

Span attributes contain only fixed operation names, venue/mode enums, counts, route templates, and HTTP status/method.
No market titles, source terms, raw books, financial payloads, raw request paths, query strings, headers, bodies, user identifiers, or exception messages are captured.
Automatic exception events and exception-derived status descriptions are disabled.
The SDK limits spans to 16 attributes of at most 128 characters, with no events or links.
Resources contain only the fixed service name and operating mode.

OTLP exporter diagnostics are replaced with a fixed message before logging because upstream diagnostics can contain collector-provided reasons or transport details.
Initialization failures disable tracing with a fixed warning; exporter and shutdown exceptions also produce fixed warnings without exception contents.
Application exceptions retain their normal behavior and are not swallowed by tracing.

A background batch processor exports up to 64 spans at a time with a bounded queue of 512 spans by default.
The queue setting accepts 64 through 8192 spans.
Queue pressure can drop telemetry instead of blocking discovery.
Network export uses the configured timeout, bounded to 10 seconds or less.
Shutdown runs provider cleanup outside the event loop and drains pending batches on a best-effort basis.
Tracing is diagnostic data, not durable audit evidence; retain the existing database audit records.

## Validation

`backend/tests/test_tracing.py` exercises the database ingestion-to-API path with an in-memory exporter, concurrent and threaded context, disabled tracing, zero sampling, exception/header/payload redaction, a failing exporter, a slow exporter with queue pressure, API lifespan cleanup, and initialization failure.
It also decodes the real serialized OTLP protobuf request while mocking only the collector transport and verifies that collector diagnostics are redacted.
The default tests do not contact an external telemetry service.
A real staging collector, retention policy, and access controls still need deployment validation.
