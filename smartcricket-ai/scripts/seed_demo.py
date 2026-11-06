"""Fill the database with demo players for a presentation: 25 players and a "Prabhu Player" account.

Each player gets a believable history over the last weeks: photo and video analyses (copies of real analyses
already in the app, so every picture, skeleton, heatmap and shot name is genuine), morning check-ins, daily drills
and quiz answers. Levels, XP and streaks then follow from the app's own rules.
Session labels, drill reasons and analysis provenance mark the generated activity
as demo data. These copied analyses are not new accuracy or player-improvement evidence.

Run again at any time: the demo players from an earlier run are removed first (with their copied files).
Other accounts (your admin, demo@example.com, ...) are never touched.

Run:  .venv/bin/python scripts/seed_demo.py
"""
import os
import random
import shutil
import sys
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import trainer  # noqa: E402
from backend.app.auth import hash_password  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.db import SessionLocal  # noqa: E402
from backend.app.models import Analysis, CoachMessage, DailyLog, Media, PlanDrill, QuizAnswer, User  # noqa: E402

PLAYER_PASSWORD = "Player@123"
PRABHU = ("Prabhu Player", "prabhu.player@example.com", "Prabhu@123")
NAMES = ["Arjun Sharma", "Rohan Iyer", "Karthik Raman", "Vikram Singh", "Aditya Rao", "Siddharth Menon",
         "Rahul Verma", "Ishaan Gupta", "Pranav Nair", "Harsh Patel", "Dhruv Reddy", "Ananya Krishnan",
         "Sneha Pillai", "Meera Joshi", "Kavya Subramanian", "Yash Kulkarni", "Nikhil Chatterjee", "Varun Bhat",
         "Aakash Das", "Manoj Kumar", "Sanjay Murugan", "Tejas Hegde", "Abhinav Mishra", "Ritika Sen",
         "Gautam Shetty"]
IMAGE_SOURCES = [1, 2, 3, 4, 7, 8, 11, 25, 43, 46]      # real photo analyses with a detected batter
VIDEO_SOURCES = [39, 40, 41, 42, 44]                    # real clips with a shot name (no AI-generated videos)
SESSIONS = ["Net session", "Morning nets", "Front-foot drill", "Match warm-up", "Evening practice", "Academy session"]
TZ = ZoneInfo("Asia/Kolkata")


def email_of(name: str) -> str:
    return name.lower().replace(" ", ".") + "@example.com"


def demo_emails() -> list[str]:
    return [email_of(n) for n in NAMES] + [PRABHU[1]]


def copy_path(src: str, folder: Path, suffix: str) -> str:
    """Hard-linked copy (no extra disk space; deleting one copy never affects the other)."""
    dst = folder / f"{uuid.uuid4().hex}{suffix}"
    if Path(src).is_dir():
        shutil.copytree(src, dst, copy_function=os.link)
    else:
        os.link(src, dst)
    return str(dst)


def remove_old(db) -> int:
    users = db.query(User).filter(User.email.in_(demo_emails())).all()
    for u in users:
        for m in u.media:
            for a in m.analyses:
                if a.output_path:
                    p = Path(a.output_path)
                    shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
            Path(m.file_path).unlink(missing_ok=True)
        db.delete(u)
    db.commit()
    return len(users)


def clone_analysis(db, user, src: Analysis, when: datetime, label: str) -> Analysis:
    m0 = src.media
    media = Media(user_id=user.id, type=m0.type, original_name=m0.original_name.split(" · ")[0],
                  session_label=f"Demo · {label}"[:100],
                  file_path=copy_path(m0.file_path, settings.upload_dir, Path(m0.file_path).suffix), uploaded_at=when)
    out = None
    if src.output_path:   # a folder of frames (video) or one picture (photo)
        out = copy_path(src.output_path, settings.output_dir, Path(src.output_path).suffix)
    a = Analysis(media=media, mode=src.mode, model=src.model, shot=src.shot, confidence=src.confidence,
                 uncertain=src.uncertain, top3=src.top3, angles=src.angles, attention=src.attention,
                 summary={**(src.summary or {}), "demo_provenance": {
                     "synthetic_activity": True, "source_analysis_id": src.id,
                     "source_created_at": src.created_at.isoformat() if src.created_at else None,
                     "synthetic_latency": True,
                     "note": "Copied analysis for demonstration; the session and activity are synthetic.",
                 }}, output_path=out, reference_id=src.reference_id, dtw=src.dtw,
                 latency_ms=int((src.latency_ms or 1500) * random.uniform(0.8, 1.2)), created_at=when)
    db.add_all([media, a])
    db.flush()
    if random.random() < 0.35:   # some players chatted with the coach about this result
        for k, msg in enumerate(src.messages[:4]):
            db.add(CoachMessage(analysis_id=a.id, role=msg.role, text=msg.text, created_at=when + timedelta(minutes=2 + k)))
    return a


def add_player(db, name, email, password, days_back, activity, keep_streak, srcs):
    joined = datetime.now(TZ) - timedelta(days=days_back + random.randint(1, 4))
    user = User(name=name, email=email, password_hash=hash_password(password), role="player", created_at=joined)
    db.add(user)
    db.flush()
    today = trainer.today()
    for back in range(days_back, -1, -1):
        day = today - timedelta(days=back)
        streak_tail = keep_streak and back < keep_streak
        if not streak_tail and random.random() > activity:
            continue
        at = lambda h: datetime.combine(day, time(h, random.randint(0, 59)), TZ)   # noqa: E731
        db.add(DailyLog(user_id=user.id, day=day, balls_faced=random.choice([0, 30, 45, 60, 80, 100, 120]),
                        soreness=random.choices(["none", "mild"], [0.85, 0.15])[0], feeling=random.randint(3, 5),
                        created_at=at(7)))
        diff = random.choice([1, 2, 2, 3])
        for code in random.sample(trainer.GENERAL + ["knee_bend", "hip_hinge", "level_shoulders", "elbow_lead"], 3):
            done = random.random() < (0.9 if streak_tail else 0.7)
            db.add(PlanDrill(user_id=user.id, day=day, code=code, title=trainer.DRILLS[code][0],
                             dose=trainer.dose(code, diff)[0], difficulty=diff, done=done,
                             done_at=at(random.randint(16, 19)) if done else None,
                             reason="Demo activity: sample drill history for a presentation."))
        q = random.choice(trainer.QUIZ)
        right = random.random() < 0.7
        db.add(QuizAnswer(user_id=user.id, day=day, question=q[0], correct=right,
                          choice=q[3] if right else random.choice([i for i in range(len(q[2])) if i != q[3]])))
        for _ in range(random.choices([0, 1, 2], [0.45, 0.4, 0.15])[0]):
            src = random.choice(srcs["video"] if random.random() < 0.4 else srcs["image"])
            clone_analysis(db, user, src, at(random.randint(16, 20)), random.choice(SESSIONS))
    db.commit()
    return user


def main():
    random.seed(7)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        print("removed earlier demo players:", remove_old(db))
        srcs = {k: [db.get(Analysis, i) for i in ids] for k, ids in (("image", IMAGE_SOURCES), ("video", VIDEO_SOURCES))}
        srcs = {k: [a for a in v if a is not None] for k, v in srcs.items()}
        for i, name in enumerate(NAMES):
            level = i % 5   # a spread of beginners to regulars
            add_player(db, name, email_of(name), PLAYER_PASSWORD, days_back=random.randint(10, 45),
                       activity=[0.25, 0.4, 0.55, 0.7, 0.85][level], keep_streak=[0, 0, 2, 4, 9][level], srcs=srcs)
        add_player(db, *PRABHU, days_back=40, activity=0.85, keep_streak=12, srcs=srcs)
        n = db.query(Analysis).join(Media).join(User).filter(User.email.in_(demo_emails())).count()
        print(f"created {len(NAMES) + 1} players with {n} analyses")


if __name__ == "__main__":
    main()
