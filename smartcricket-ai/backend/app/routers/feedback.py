"""Player feedback: players send it from their Feedback tab, administrators read and reply."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_admin, current_player
from ..db import get_db
from ..models import Feedback, User, now
from ..serialize import timestamp

router = APIRouter(prefix="/api", tags=["feedback"])
CATEGORIES = ("training", "coach", "analysis", "app", "bug", "idea")
TAGS = ("Easy to use", "Helpful drills", "Accurate analysis", "Motivating", "Too hard", "Too easy",
        "Confusing", "Slow", "Wrong result", "Needs more drills")


class FeedbackIn(BaseModel):
    category: Literal[CATEGORIES]
    rating: int = Field(ge=1, le=5)
    message: str = Field(min_length=3, max_length=1000)
    tags: list[Literal[TAGS]] = Field(default_factory=list, max_length=len(TAGS))
    page: str = Field(default="", max_length=60)

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Please write at least a few words")
        return v

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class StatusIn(BaseModel):
    status: Literal["new", "read"]


class ReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=1000)

    @field_validator("reply")
    @classmethod
    def strip_reply(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Write a reply first")
        return v


def feedback_out(f: Feedback, with_player: bool = True) -> dict:
    out = {"id": f.id, "category": f.category, "rating": f.rating, "message": f.message, "tags": f.tags or [],
           "page": f.page, "status": f.status, "reply": f.reply, "replied_at": timestamp(f.replied_at),
           "created_at": timestamp(f.created_at)}
    if with_player:
        out["player"] = {"id": f.user.id, "name": f.user.name, "email": f.user.email}
    return out


def _get(db: Session, feedback_id: int) -> Feedback:
    f = db.get(Feedback, feedback_id)
    if f is None:
        raise HTTPException(404, "Feedback not found")
    return f


@router.post("/feedback", status_code=201)
def send_feedback(body: FeedbackIn, user: User = Depends(current_player), db: Session = Depends(get_db)):
    f = Feedback(user_id=user.id, **body.model_dump())
    db.add(f)
    db.commit()
    return feedback_out(f, with_player=False)


@router.get("/feedback/mine")
def my_feedback(user: User = Depends(current_player), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).where(Feedback.user_id == user.id)
                      .order_by(Feedback.created_at.desc(), Feedback.id.desc())).all()
    return {"tags": TAGS, "items": [feedback_out(f, with_player=False) for f in rows]}


@router.get("/admin/feedback")
def list_feedback(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).order_by(Feedback.created_at.desc(), Feedback.id.desc())).all()
    return [feedback_out(f) for f in rows]


@router.post("/admin/feedback/{feedback_id}")
def set_status(feedback_id: int, body: StatusIn, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    f = _get(db, feedback_id)
    f.status = body.status
    db.commit()
    return feedback_out(f)


@router.post("/admin/feedback/{feedback_id}/reply")
def reply(feedback_id: int, body: ReplyIn, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    f = _get(db, feedback_id)
    f.reply, f.replied_at, f.status = body.reply, now(), "read"
    db.commit()
    return feedback_out(f)


@router.delete("/admin/feedback/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: int, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    db.delete(_get(db, feedback_id))
    db.commit()
