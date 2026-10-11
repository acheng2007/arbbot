"""Derived text from immutable evidence, isolated from API/worker event loops."""

import asyncio
import base64
import hashlib
import json
import sys
from html.parser import HTMLParser
from io import BytesIO
from typing import Literal

from pydantic import Field

from arbbot.domain import Model
from arbbot.sources.models import MAX_CONTENT_BYTES

MAX_PAGES = 100
MAX_TEXT = 300_000
EXTRACTOR_VERSION = "source-text-v1:pypdf-6.20.0"
SLOTS = asyncio.Semaphore(4)


class TextPage(Model):
    page: int | None = None
    text: str


class DerivedText(Model):
    artifact_id: str
    content_digest: str
    extractor_version: str = EXTRACTOR_VERSION
    status: Literal["complete", "partial", "unavailable"]
    pages: tuple[TextPage, ...] = ()
    text_digest: str | None = None
    reason: str | None = None
    page_limit: int = MAX_PAGES
    text_limit: int = MAX_TEXT
    time_limit_seconds: float = Field(default=3, gt=0)


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def extract(content, content_type, artifact_id):
    fields = {"artifact_id": artifact_id, "content_digest": hashlib.sha256(content).hexdigest()}
    if len(content) > MAX_CONTENT_BYTES:
        return DerivedText(**fields, status="unavailable", reason="source_too_large")
    try:
        partial = False
        pages = []
        if content_type == "application/pdf":
            from pypdf import PdfReader, overwrite_configuration

            overwrite_configuration(
                maximum_declared_stream_length=2_000_000,
                array_based_stream_maximum_output_length=2_000_000,
                jbig2_maximum_output_length=2_000_000,
                lzw_maximum_output_length=2_000_000,
                run_length_maximum_output_length=2_000_000,
                zlib_maximum_output_length=2_000_000,
                brotli_maximum_output_length=2_000_000,
                stream_decoding_work_maximum_length=4_000_000,
            )

            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                return DerivedText(**fields, status="unavailable", reason="encrypted_pdf")
            partial = len(reader.pages) > MAX_PAGES
            remaining = MAX_TEXT
            for index, page in enumerate(reader.pages[:MAX_PAGES]):
                # Reject expansion bombs before decoding a content stream.
                streams = page.get("/Contents")
                streams = streams if isinstance(streams, list) else [streams] if streams else []
                if any(len(stream.get_object().get_data()) > 2_000_000 for stream in streams):
                    return DerivedText(
                        **fields, status="unavailable", reason="pdf_stream_too_large"
                    )
                text = page.extract_text() or ""
                if len(text) > remaining:
                    partial = True
                pages.append(TextPage(page=index + 1, text=text[:remaining]))
                remaining -= min(len(text), remaining)
                if remaining == 0:
                    partial = partial or index + 1 < len(reader.pages)
                    break
        elif content_type in {"text/plain", "text/html"}:
            text = content.decode("utf-8", errors="strict")
            if content_type == "text/html":
                parser = VisibleHTML()
                parser.feed(text)
                text = "".join(parser.parts)
            partial = len(text) > MAX_TEXT
            pages = [TextPage(text=text[:MAX_TEXT])]
        else:
            return DerivedText(**fields, status="unavailable", reason="unsupported_text_type")
        if not any(page.text.strip() for page in pages):
            return DerivedText(**fields, status="unavailable", reason="no_extractable_text")
        digest = hashlib.sha256(
            json.dumps([p.model_dump() for p in pages], sort_keys=True).encode()
        ).hexdigest()
        return DerivedText(
            **fields,
            status="partial" if partial else "complete",
            pages=tuple(pages),
            text_digest=digest,
            reason="extraction_limit_reached" if partial else None,
        )
    except Exception:
        return DerivedText(**fields, status="unavailable", reason="extraction_failed")


async def derive_text(content, content_type, artifact_id, *, limit_seconds=3):
    fields = {
        "artifact_id": artifact_id,
        "content_digest": hashlib.sha256(content).hexdigest(),
        "time_limit_seconds": limit_seconds,
    }
    if len(content) > MAX_CONTENT_BYTES:
        return DerivedText(**fields, status="unavailable", reason="source_too_large")
    async with SLOTS:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "arbbot.sources.text",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            return DerivedText(**fields, status="unavailable", reason="extractor_start_failed")
        try:
            request = json.dumps(
                {
                    "content": base64.b64encode(content).decode(),
                    "type": content_type,
                    "id": artifact_id,
                }
            ).encode()
            async with asyncio.timeout(limit_seconds):
                output, _ = await process.communicate(request)
            if process.returncode != 0:
                return DerivedText(**fields, status="unavailable", reason="extractor_failed")
            result = DerivedText.model_validate_json(output)
            return result.model_copy(update={"time_limit_seconds": limit_seconds})
        except (ValueError, UnicodeError):
            return DerivedText(**fields, status="unavailable", reason="extractor_invalid_result")
        except TimeoutError:
            return DerivedText(**fields, status="unavailable", reason="extraction_timeout")
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()


def main():
    # A malicious compressed PDF cannot exhaust the parent process's memory.
    import resource

    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (512_000_000, 512_000_000))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    request = json.loads(sys.stdin.buffer.read(7_000_000))
    result = extract(base64.b64decode(request["content"]), request["type"], request["id"])
    print(result.model_dump_json())


if __name__ == "__main__":
    main()
