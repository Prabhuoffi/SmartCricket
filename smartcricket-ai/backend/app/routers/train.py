"""Training page and progress page: daily plan, check-in, quiz, coach questions, weekly report (module M9)."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import coach, trainer
from ..auth import current_user
from ..db import get_db
from ..models import DailyLog, LiveSession, PlanDrill, QuizAnswer, Reflection, TrainingChat, User

router = APIRouter(prefix="/api/train", tags=["training"])
log = logging.getLogger("smartcricket")


class CheckIn(BaseModel):
    balls_faced: int | None = Field(default=None, ge=0, le=2000)
    soreness: Literal["none", "mild", "stop"]
    feeling: int | None = Field(default=None, ge=1, le=5)


class Done(BaseModel):
    done: bool = True


class Choice(BaseModel):
    choice: int = Field(ge=0, le=3)


class Answer(BaseModel):
    analysis_id: int
    answer: str = Field(min_length=1, max_length=30)


class LiveIn(BaseModel):
    drill_id: int | None = None
    title: str = Field(min_length=1, max_length=120)
    duration_s: int = Field(ge=1, le=4 * 3600)
    reps: int = Field(default=0, ge=0, le=10000)
    hold_s: int = Field(default=0, ge=0, le=4 * 3600)
    completed: bool = False
    stats: dict | None = None


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=500)


def today_payload(db: Session, c: trainer.Ctx) -> dict:
    plan = trainer.plan_for(db, c)
    log_ = c.logs.get(c.day)
    chat = db.scalars(select(TrainingChat).where(TrainingChat.user_id == c.user.id)
                      .order_by(TrainingChat.id.desc()).limit(20)).all()[::-1]
    return {
        "date": c.day.isoformat(),
        "checkin": {"balls_faced": log_.balls_faced, "soreness": log_.soreness, "feeling": log_.feeling} if log_ else None,
        "plan": [trainer.drill_out(d) for d in plan],
        "rest_day": any(d.code == "rest" for d in plan),
        "difficulty": trainer.difficulty(c, c.day),
        "reflection": trainer.reflection_question(c),
        "quiz": trainer.quiz_today(c),
        "chat": [{"role": m.role, "text": m.text} for m in chat],
        "status": trainer.status(c),
    }


@router.get("/status")
def status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Small summary for the top bar and the dashboard: level, XP, streak and practice days."""
    return trainer.status(trainer.load(user, db))


@router.get("/today")
def today(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return today_payload(db, trainer.load(user, db))


@router.post("/checkin")
def checkin(body: CheckIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = trainer.load(user, db)
    row = c.logs.get(c.day) or DailyLog(user_id=user.id, day=c.day)
    row.balls_faced, row.soreness, row.feeling = body.balls_faced, body.soreness, body.feeling
    db.add(row)
    db.commit()
    c.logs[c.day] = row
    trainer.replan_today(db, c)
    return today_payload(db, c)


@router.post("/drills/{drill_id}")
def mark_drill(drill_id: int, body: Done, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(PlanDrill, drill_id)
    if not d or d.user_id != user.id:
        raise HTTPException(404, "Drill not found")
    if d.day != trainer.today():
        raise HTTPException(409, "Only today's drills can be changed")
    before = trainer.status(trainer.load(user, db))["level"]
    d.done, d.done_at = body.done, datetime.now(timezone.utc) if body.done else None
    db.commit()
    st = trainer.status(trainer.load(user, db))
    return {"done": d.done, "status": st, "level_up": st["level"] > before}


@router.post("/quiz")
def answer_quiz(body: Choice, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = trainer.load(user, db)
    if c.day in c.quiz:
        raise HTTPException(409, "You have already answered today's question")
    q = trainer.quiz_today(c)
    _, _, options, right, why = trainer.QUIZ_BY_ID[q["id"]]
    if body.choice >= len(options):
        raise HTTPException(422, "Not one of the options")
    before = trainer.status(c)["level"]
    row = QuizAnswer(user_id=user.id, day=c.day, question=q["id"], choice=body.choice, correct=body.choice == right)
    db.add(row)
    db.commit()
    c.quiz[c.day] = row
    st = trainer.status(c)
    return {"correct": row.correct, "answer": right, "why": why, "xp": trainer.XP_RULES["quiz_right" if row.correct else "quiz_wrong"],
            "status": st, "level_up": st["level"] > before}


@router.post("/live-sessions", status_code=201)
def save_live(body: LiveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Save the summary of a live-mirror session. Only numbers are stored, never camera images."""
    c = trainer.load(user, db)
    if body.drill_id is not None:
        d = db.get(PlanDrill, body.drill_id)
        if not d or d.user_id != user.id:
            raise HTTPException(404, "Drill not found")
    before = trainer.status(c)["level"]
    stats = {k: v for k, v in (body.stats or {}).items() if isinstance(v, (int, float, str, bool)) or v is None}
    row = LiveSession(user_id=user.id, day=c.day, drill_id=body.drill_id, title=body.title.strip(), duration_s=body.duration_s,
                      reps=body.reps, hold_s=body.hold_s, completed=body.completed, stats=stats)
    db.add(row)
    db.commit()
    c.live.append(row)
    st = trainer.status(c)
    return {"id": row.id, "xp": trainer.XP_RULES["live"], "status": st, "level_up": st["level"] > before}


@router.post("/reflection")
def reflect(body: Answer, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = trainer.load(user, db)
    q = trainer.reflection_question(c)
    if not q or q["analysis_id"] != body.analysis_id or body.answer not in q["options"]:
        raise HTTPException(409, "There is no open question for this analysis")
    db.add(Reflection(user_id=user.id, analysis_id=body.analysis_id, question=q["question"], answer=body.answer))
    db.commit()
    return {"reply": trainer.REFLECTION_REPLIES.get(body.answer, "Thanks, noted.")}


@router.post("/chat")
async def chat(body: Message, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = trainer.load(user, db)
    text = body.text.strip()
    try:
        answer = await run_in_threadpool(trainer.chat_reply, db, c, text)
    except coach.CoachBusy:
        raise HTTPException(503, "The AI Coach is busy right now (the Gemini servers are overloaded). "
                                 "Please try again in a minute.")
    except Exception:
        log.exception("training chat failed user=%s", user.id)
        raise HTTPException(502, "The coach service is not responding, please try again later")
    db.add_all([TrainingChat(user_id=user.id, role="user", text=text),
                TrainingChat(user_id=user.id, role="coach", text=answer)])
    db.commit()
    return {"reply": answer}


@router.get("/progress")
def progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = trainer.load(user, db)
    this_week = trainer.monday(c.day)
    weeks = [trainer.week_stats(c, this_week - timedelta(weeks=i)) for i in range(7, -1, -1)]
    reports = {r.week_start.isoformat(): r.text for r in
               db.scalars(select(trainer.WeeklyReport).where(trainer.WeeklyReport.user_id == user.id))}
    for w in weeks:
        w["summary"] = reports.get(w["week_start"])
    days = trainer.active_days(c)
    st = trainer.status(c)
    live = [{"id": s.id, "title": s.title, "day": s.day.isoformat(), "duration_s": s.duration_s, "reps": s.reps,
             "hold_s": s.hold_s, "completed": s.completed, "stats": s.stats or {}} for s in reversed(c.live[-8:])]
    return {"status": st, "weeks": weeks, "xp_rules": trainer.XP_RULES, "live_sessions": live,
            "difficulty": trainer.difficulty(c, c.day),
            "totals": {"drills_done": sum(d.done for d in c.drills), "checkins": len(c.logs),
                       "quiz_answered": len(c.quiz), "quiz_correct": sum(q.correct for q in c.quiz.values()),
                       "balls_faced": sum(l.balls_faced or 0 for l in c.logs.values()), "active_days": len(days),
                       "full_photos": trainer.full_photos(c), "plan_weeks": trainer.plan_weeks(c)}}


@router.post("/week/summary")
async def week_summary(offset: int = 0, refresh: bool = False, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Coach-written summary of one week (offset 0 = this week, 1 = last week)."""
    if not 0 <= offset <= 7:
        raise HTTPException(422, "offset must be between 0 and 7")
    c = trainer.load(user, db)
    start = trainer.monday(c.day) - timedelta(weeks=offset)
    report = await run_in_threadpool(trainer.weekly_summary, db, c, start, refresh)
    return {"week_start": report.week_start.isoformat(), "text": report.text, "stats": report.stats}
