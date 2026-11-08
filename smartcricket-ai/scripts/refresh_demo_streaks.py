"""Add missing, labeled practice activity to the known demonstration accounts.

Preview: .venv/bin/python scripts/refresh_demo_streaks.py
Apply:   .venv/bin/python scripts/refresh_demo_streaks.py --apply

Apply creates a database backup first. Existing rows, media, measurements,
passwords and real-player accounts are never replaced or deleted. A refresh is
manual: the app does not manufacture daily activity in the background.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from backend.app import trainer  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.db import SessionLocal  # noqa: E402
from backend.app.models import User  # noqa: E402
from scripts.demo_player_history import TZ, build_history  # noqa: E402
from scripts.seed_demo import NAMES, PRABHU, email_of  # noqa: E402

DEMO_ACCOUNTS = {email_of(name): name for name in NAMES} | {
    PRABHU[1]: PRABHU[0], "demo@example.com": "Demo Player",
}


def refresh(db, at: datetime, apply: bool = False) -> list[dict]:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Use a timezone-aware refresh time")
    at = at.astimezone(TZ)
    day = at.date()
    result = []
    users = db.scalars(select(User).where(User.role == "player", User.email.in_(DEMO_ACCOUNTS))
                       .order_by(User.id)).all()
    for user in users:
        # Both identity fields must match the known fixture, not just an email domain.
        if user.name != DEMO_ACCOUNTS[user.email]:
            continue
        c = trainer.load(user, db)
        days = trainer.active_days(c)
        before = trainer.streaks(days, day)[0]
        length = 12 if user.email == PRABHU[1] else 7 if user.email == "demo@example.com" else (2, 3, 4, 5, 7)[user.id % 5]
        joined = trainer.local_day(user.created_at)
        length = min(length, (day - joined).days + 1)
        if length < 1:
            continue
        history = build_history(user, c.analyses, day, at, length)
        existing_plan_days = {row.day for row in c.drills}
        logs = [row for row in history["logs"] if row.day not in c.logs]
        new_days = {row.day for row in logs}
        drills = [row for row in history["drills"] if row.day in new_days and row.day not in existing_plan_days]
        quizzes = [row for row in history["quizzes"] if row.day in new_days and row.day not in c.quiz]
        if apply:
            db.add_all(logs + drills + quizzes)
            db.flush()
        # New check-ins establish only the missing days; original activity is kept.
        after = trainer.streaks(set(days) | {row.day for row in logs}, day)[0]
        result.append({"id": user.id, "name": user.name, "synthetic_activity": True,
                       "streak_before": before, "streak_after": after,
                       "added_checkins": len(logs), "added_drills": len(drills),
                       "added_quizzes": len(quizzes)})
    return result


def backup_database(at: datetime) -> Path:
    folder = ROOT / "data" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    url = make_url(settings.database_url)
    tag = at.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if url.get_backend_name() == "postgresql":
        binary = shutil.which("pg_dump")
        if binary is None:
            raise RuntimeError("pg_dump is required before updating demo activity")
        path = folder / f"before-demo-streaks-{tag}.dump"
        env = os.environ.copy()
        for key, value in {"PGHOST": url.host, "PGPORT": url.port, "PGUSER": url.username,
                           "PGPASSWORD": url.password, "PGDATABASE": url.database}.items():
            if value is not None:
                env[key] = str(value)
        if "sslmode" in url.query:
            env["PGSSLMODE"] = url.query["sslmode"]
        with path.open("xb") as output:
            os.chmod(path, 0o600)
            run = subprocess.run([binary, "--format=custom", "--no-owner"], env=env,
                                 stdout=output, stderr=subprocess.PIPE, timeout=120)
        if run.returncode:
            raise RuntimeError("Database backup failed; no demo activity was updated")
    elif url.get_backend_name() == "sqlite" and url.database not in (None, ":memory:"):
        path = folder / f"before-demo-streaks-{tag}.sqlite3"
        with path.open("xb"):
            os.chmod(path, 0o600)
        with sqlite3.connect(url.database) as source, sqlite3.connect(path) as destination:
            source.backup(destination)
    else:
        raise RuntimeError("This database type needs a supported backup before refresh")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and add missing demo activity")
    args = parser.parse_args()
    at = datetime.now(timezone.utc)
    with SessionLocal() as db:
        preview = refresh(db, at)
    changes = any(row[key] for row in preview for key in ("added_checkins", "added_drills", "added_quizzes"))
    if args.apply and changes:
        backup = backup_database(at)
        with SessionLocal.begin() as db:
            rows = refresh(db, at, apply=True)
        audit = backup.with_suffix(".activity.json")
        audit.write_text(json.dumps({"synthetic_activity": True, "at": at.isoformat(),
                                     "backup": backup.name, "players": rows}, indent=2) + "\n")
        print(f"Backup: {backup.relative_to(ROOT)}")
    else:
        rows = preview
    print(json.dumps({"applied": args.apply and changes, "demo_players": len(rows),
                      "added_checkins": sum(row["added_checkins"] for row in rows),
                      "added_drills": sum(row["added_drills"] for row in rows),
                      "added_quizzes": sum(row["added_quizzes"] for row in rows),
                      "streak_min": min((row["streak_after"] for row in rows), default=0),
                      "streak_max": max((row["streak_after"] for row in rows), default=0)}, indent=2))


if __name__ == "__main__":
    main()
