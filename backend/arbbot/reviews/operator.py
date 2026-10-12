"""Local operator imports use the same validation and concurrency as authenticated APIs."""

import argparse
import asyncio
import getpass
import json
from pathlib import Path

from pydantic import Field

from arbbot.config import Settings
from arbbot.domain import Model
from arbbot.execution.models import ConfigurationWrite
from arbbot.execution.repository import ExecutionRepository
from arbbot.reviews.models import Actor, DecisionWrite, DraftWrite
from arbbot.reviews.repository import ReviewRepository
from arbbot.storage.database import Database


class CaptureRequest(Model):
    market_id: str = Field(min_length=1, max_length=512)
    url: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=100)


async def operate(args):
    if (args.command == "capture") != (args.kind == "source"):
        raise ValueError("Source requests use capture; reviewed records use validate or import")
    if args.command == "capture":
        request = CaptureRequest.model_validate_json(args.file.read_text())
        from arbbot.sources.fetch import SourceFetcher
        from arbbot.sources.models import SourceCapture
        from arbbot.sources.repository import SourceRepository
        from arbbot.storage.repository import Repository

        settings = Settings()
        database = Database(settings)
        try:
            market = await Repository(database).market(settings.mode, request.market_id)
            if market is None:
                raise LookupError("Market not found in this mode")
            content, content_type, retrieved_at = await SourceFetcher().read(request.url)
            artifact = await SourceRepository(database).record(
                SourceCapture(
                    mode=settings.mode,
                    venue=market.venue,
                    market_id=market.id,
                    url=request.url,
                    label=request.label,
                    content=content,
                    content_type=content_type,
                    retrieved_at=retrieved_at,
                    details={"local_operator": getpass.getuser()},
                )
            )
            print(json.dumps({"artifact_id": artifact.id, "content_hash": artifact.content_digest}))
        finally:
            await database.close()
        return
    model = {"draft": DraftWrite, "decision": DecisionWrite, "configuration": ConfigurationWrite}[
        args.kind
    ]
    request = model.model_validate_json(args.file.read_text())
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "schema_valid": True,
                    "imported": False,
                    "note": "Repository evidence and concurrency are checked on import",
                }
            )
        )
        return
    settings = Settings()
    database = Database(settings)
    actor = Actor(issuer="local-operator", subject=getpass.getuser())
    try:
        reviews = ReviewRepository(database)
        if args.kind == "draft":
            if not args.market_id:
                raise ValueError("Draft import requires --market-id")
            result = await reviews.save_draft(settings.mode, args.market_id, request, actor)
        elif args.kind == "decision":
            result = await reviews.save_decision(settings.mode, request, actor)
        else:
            result = await ExecutionRepository(database).save(settings.mode, request, actor)
        print(json.dumps({"revision_id": result.id, "operator": actor.subject}))
    finally:
        await database.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "import", "capture"))
    parser.add_argument("kind", choices=("draft", "decision", "configuration", "source"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--market-id")
    asyncio.run(operate(parser.parse_args()))


if __name__ == "__main__":
    main()
