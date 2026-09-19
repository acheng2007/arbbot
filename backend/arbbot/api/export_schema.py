"""Export contracts without starting services or connecting to a database."""

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from arbbot.api.app import create_app
from arbbot.domain import Review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviews", action="store_true")
    args = parser.parse_args()
    schema = TypeAdapter(list[Review]).json_schema() if args.reviews else create_app().openapi()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, indent=2) + "\n")


if __name__ == "__main__":
    main()
