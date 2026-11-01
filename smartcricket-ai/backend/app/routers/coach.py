"""POST /api/coach/{analysis_id}: ask the coach about one stored analysis (FR-14)."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import coach, trainer
from ..auth import current_user
from ..db import get_db
from ..models import CoachMessage, User
from .analyses import owned_analysis

router = APIRouter(prefix="/api/coach", tags=["coach"])
log = logging.getLogger("smartcricket")


class Question(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post("/{analysis_id}")
async def ask(analysis_id: int, q: Question, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = owned_analysis(analysis_id, user, db)
    history = [(m.role, m.text) for m in a.messages]
    player = trainer.player_facts(db, trainer.load(user, db))   # the same coach knows the plan on every page
    try:
        answer = await run_in_threadpool(coach.reply, a, history, q.text.strip(), player)
    except coach.CoachBusy:
        raise HTTPException(503, "The AI Coach is busy right now (the Gemini servers are overloaded). "
                                 "Please try again in a minute.")
    except Exception:
        log.exception("coach call failed analysis=%s", analysis_id)
        raise HTTPException(502, "The coach service is not responding, please try again later")
    db.add_all([CoachMessage(analysis_id=a.id, role="user", text=q.text.strip()),
                CoachMessage(analysis_id=a.id, role="coach", text=answer)])
    db.commit()
    return {"reply": answer}
