#!/usr/bin/env python3
"""CLI entrypoint for DDYs MongoDB migrations.

Usage::

    python scripts/migrate.py up        # apply pending migrations (default)
    python scripts/migrate.py status    # show applied vs pending
    python scripts/migrate.py down      # roll back the most recent migration

Honors MONGO_URL and DB_NAME from the backend ``.env`` file just like
``server.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Make backend/ importable when run from the repo root.
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")


async def _run(action: str) -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("MONGO_URL and DB_NAME must be set.", file=sys.stderr)
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    try:
        from migrations import migration_status, rollback_last, run_migrations

        if action == "up":
            result = await run_migrations(db)
        elif action == "status":
            result = await migration_status(db)
        elif action == "down":
            result = await rollback_last(db)
        else:  # pragma: no cover - argparse guards
            print(f"Unknown action: {action}", file=sys.stderr)
            return 2

        print(json.dumps(result, indent=2, default=str))
        return 0
    finally:
        client.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="DDYs MongoDB migrations")
    parser.add_argument(
        "action",
        nargs="?",
        default="up",
        choices=["up", "down", "status"],
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.action))


if __name__ == "__main__":
    raise SystemExit(main())
