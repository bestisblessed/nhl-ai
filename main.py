from __future__ import annotations

import argparse
import json
from datetime import date

from config import Settings
from ingestion.pipeline import backfill, load_seed, refresh


def main() -> None:
    parser = argparse.ArgumentParser(description="NHL take-home ingestion pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="load the supplied 2022-23 CSV")
    backfill_parser = sub.add_parser("backfill", help="load all configured seasons")
    backfill_parser.add_argument("--offline-seed-only", action="store_true")
    refresh_parser = sub.add_parser("refresh", help="run the daily incremental refresh")
    refresh_parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        help="override today's date (YYYY-MM-DD) for recovery/testing",
    )
    args = parser.parse_args()
    settings = Settings()
    if args.command == "seed":
        result = {"seed": load_seed(settings)}
    elif args.command == "backfill":
        result = backfill(settings, offline_seed_only=args.offline_seed_only)
    else:
        result = refresh(settings, as_of=args.as_of)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
