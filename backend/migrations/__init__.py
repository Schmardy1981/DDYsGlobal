"""DDYs MongoDB migration runner.

Each migration is a Python module in this package whose filename starts with a
zero-padded version number (e.g. ``000_initial_indexes.py``). Modules must
expose two async coroutines::

    async def up(db) -> None: ...
    async def down(db) -> None: ...

Applied migrations are tracked in the ``_migrations`` collection so that
re-runs are idempotent. The runner is invoked from the FastAPI startup hook
and from ``scripts/migrate.py``.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable

logger = logging.getLogger(__name__)

MIGRATIONS_COLLECTION = "_migrations"
_VERSION_RE = re.compile(r"^(\d+)_(.+)$")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    module_name: str
    up: Callable[[object], Awaitable[None]]
    down: Callable[[object], Awaitable[None]]


def discover_migrations() -> list[Migration]:
    """Find migration modules in this package, sorted by version."""
    import sys

    pkg = sys.modules[__name__]
    pkg_name = __name__

    migrations: list[Migration] = []
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        match = _VERSION_RE.match(mod_info.name)
        if not match:
            continue
        version = int(match.group(1))
        name = match.group(2)
        module = importlib.import_module(f"{pkg_name}.{mod_info.name}")
        up = getattr(module, "up", None)
        down = getattr(module, "down", None)
        if not callable(up) or not callable(down):
            logger.warning("Skipping migration %s: missing up/down", mod_info.name)
            continue
        migrations.append(
            Migration(
                version=version,
                name=name,
                module_name=mod_info.name,
                up=up,
                down=down,
            )
        )
    migrations.sort(key=lambda m: m.version)
    _assert_unique_versions(migrations)
    return migrations


def _assert_unique_versions(migrations: Iterable[Migration]) -> None:
    seen: dict[int, str] = {}
    for m in migrations:
        if m.version in seen:
            raise RuntimeError(
                f"Duplicate migration version {m.version}: "
                f"{seen[m.version]} and {m.module_name}"
            )
        seen[m.version] = m.module_name


async def applied_versions(db) -> set[int]:
    cursor = db[MIGRATIONS_COLLECTION].find({}, {"_id": 0, "version": 1})
    docs = await cursor.to_list(length=None)
    return {d["version"] for d in docs}


async def run_migrations(db) -> dict:
    """Apply all pending migrations in order. Idempotent.

    Returns a summary dict with applied and skipped counts.
    """
    migrations = discover_migrations()
    already = await applied_versions(db)

    applied: list[str] = []
    skipped: list[str] = []

    for m in migrations:
        if m.version in already:
            skipped.append(m.module_name)
            continue
        logger.info("Applying migration %s", m.module_name)
        await m.up(db)
        await db[MIGRATIONS_COLLECTION].insert_one(
            {
                "version": m.version,
                "name": m.name,
                "module": m.module_name,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        applied.append(m.module_name)
        logger.info("Migration %s applied", m.module_name)

    return {
        "applied": applied,
        "skipped": skipped,
        "total": len(migrations),
    }


async def rollback_last(db) -> dict:
    """Roll back the most recently applied migration."""
    migrations = {m.version: m for m in discover_migrations()}
    last = (
        await db[MIGRATIONS_COLLECTION]
        .find({}, {"_id": 0})
        .sort("version", -1)
        .to_list(length=1)
    )
    if not last:
        return {"rolled_back": None, "message": "No migrations to roll back."}

    rec = last[0]
    m = migrations.get(rec["version"])
    if not m:
        raise RuntimeError(
            f"Cannot roll back: migration module {rec['module']} not found."
        )
    logger.info("Rolling back migration %s", m.module_name)
    await m.down(db)
    await db[MIGRATIONS_COLLECTION].delete_one({"version": m.version})
    return {"rolled_back": m.module_name}


async def migration_status(db) -> dict:
    """Return a status report: applied vs. pending."""
    migrations = discover_migrations()
    already = await applied_versions(db)
    return {
        "applied": sorted(already),
        "pending": [m.module_name for m in migrations if m.version not in already],
        "total": len(migrations),
    }
