"""Saved player goals and comparisons against their own earlier captures."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..models import PracticeGoal, User, now
from ..practice import JOINTS, PracticeError, capture_measurements, compare_analyses, joint_label
from ..practice_preview import capture_preview_bytes
from ..serialize import analysis_out, timestamp
from .analyses import owned_analysis

router = APIRouter(prefix="/api/practice", tags=["practice"])


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=1000)
    baseline_id: int = Field(gt=0)
    baseline_frame: int | None = Field(default=None, ge=0, le=63)
    focus_joint: str
    target_deg: float | None = Field(default=None, ge=0, le=180)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter a goal title")
        return value.strip()

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value):
        return value.strip()

    @field_validator("focus_joint")
    @classmethod
    def known_joint(cls, value):
        if value not in JOINTS:
            raise ValueError("Choose one of the eight measured joints")
        return value


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    focus_joint: str | None = None
    target_deg: float | None = Field(default=None, ge=0, le=180)
    due_date: date | None = None
    status: Literal["active", "completed", "archived"] | None = None
    retest_id: int | None = Field(default=None, gt=0)
    baseline_frame: int | None = Field(default=None, ge=0, le=63)
    retest_frame: int | None = Field(default=None, ge=0, le=63)
    same_setup: bool | None = None

    @field_validator("title", "notes", "focus_joint", "status", "same_setup")
    @classmethod
    def nonnull_values(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        return GoalCreate.title_not_blank(value)

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value):
        return value.strip()

    @field_validator("focus_joint")
    @classmethod
    def known_joint(cls, value):
        return GoalCreate.known_joint(value)


def owned_goal(goal_id: int, user: User, db: Session) -> PracticeGoal:
    goal = db.scalar(select(PracticeGoal).where(PracticeGoal.id == goal_id, PracticeGoal.user_id == user.id))
    if goal is None:
        raise HTTPException(404, "Practice goal not found")
    return goal


def goal_out(goal: PracticeGoal) -> dict:
    return {"id": goal.id, "title": goal.title, "notes": goal.notes, "focus_joint": goal.focus_joint,
            "target_deg": goal.target_deg, "due_date": goal.due_date.isoformat() if goal.due_date else None,
            "status": goal.status, "created_at": timestamp(goal.created_at), "updated_at": timestamp(goal.updated_at),
            "baseline": analysis_out(goal.baseline, brief=True) if goal.baseline else None,
            "retest": analysis_out(goal.retest, brief=True) if goal.retest else None,
            "baseline_frame": goal.baseline_frame, "retest_frame": goal.retest_frame, "same_setup": goal.same_setup}


def comparison_for_user(user: User, db: Session, baseline_id: int, retest_id: int,
                        baseline_frame: int | None = None, retest_frame: int | None = None,
                        same_setup: bool = False) -> dict:
    baseline = owned_analysis(baseline_id, user, db)
    retest = owned_analysis(retest_id, user, db)
    try:
        return compare_analyses(baseline, retest, baseline_frame, retest_frame, same_setup)
    except PracticeError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/compare")
def compare(baseline_id: int = Query(gt=0), retest_id: int = Query(gt=0),
            baseline_frame: int | None = Query(default=None, ge=0, le=63),
            retest_frame: int | None = Query(default=None, ge=0, le=63), same_setup: bool = False,
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    return comparison_for_user(user, db, baseline_id, retest_id, baseline_frame, retest_frame, same_setup)


@router.get("/captures/{analysis_id}/preview")
def preview(analysis_id: int, frame: int | None = Query(default=None, ge=0, le=63),
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    analysis = owned_analysis(analysis_id, user, db)
    try:
        content = capture_preview_bytes(analysis, frame)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except PracticeError as error:
        raise HTTPException(400, str(error)) from error
    return Response(content, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/goals")
def goals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(PracticeGoal).where(PracticeGoal.user_id == user.id)
                      .order_by(PracticeGoal.created_at.desc(), PracticeGoal.id.desc())).all()
    return {"goals": [goal_out(g) for g in rows], "joints": [{"key": j, "label": joint_label(j)} for j in JOINTS],
            "active_count": sum(g.status == "active" for g in rows), "min_visibility": settings.min_visibility}


def _measured_joint(analysis, frame, joint):
    try:
        measurements, frame, _ = capture_measurements(analysis, frame)
    except PracticeError as error:
        raise HTTPException(400, str(error)) from error
    if measurements.get(joint) is None:
        raise HTTPException(400, "The focus joint must be clearly measured in the selected capture and frame.")
    return frame


@router.post("/goals", status_code=201)
def create_goal(body: GoalCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    baseline = owned_analysis(body.baseline_id, user, db)
    frame = _measured_joint(baseline, body.baseline_frame, body.focus_joint)
    goal = PracticeGoal(user_id=user.id, title=body.title, notes=body.notes, focus_joint=body.focus_joint,
                        target_deg=body.target_deg, due_date=body.due_date, baseline=baseline, baseline_frame=frame)
    db.add(goal)
    db.commit()
    return goal_out(goal)


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = owned_goal(goal_id, user, db)
    changes = body.model_dump(exclude_unset=True)
    focus = changes.get("focus_joint", goal.focus_joint)
    baseline_frame = changes.get("baseline_frame", goal.baseline_frame)
    retest_id = changes.get("retest_id", goal.retest_id)
    retest_frame = changes.get("retest_frame", goal.retest_frame)
    if "retest_id" in changes and retest_id != goal.retest_id and "retest_frame" not in changes:
        retest_frame = None  # a new clip starts at its own key frame
    if "retest_frame" in changes and retest_id is None and retest_frame is not None:
        raise HTTPException(400, "Choose a retest capture before selecting its frame.")
    retest = owned_analysis(retest_id, user, db) if retest_id is not None else None
    evidence_changed = bool({"focus_joint", "baseline_frame", "retest_id", "retest_frame"} & changes.keys())
    validate_pair = evidence_changed or changes.get("same_setup") is True or changes.get("status") == "completed"
    if validate_pair and retest is not None:
        if goal.baseline is None:
            raise HTTPException(409, "The baseline was deleted. Create a new goal with an available baseline.")
        baseline_frame = _measured_joint(goal.baseline, baseline_frame, focus)
        retest_frame = _measured_joint(retest, retest_frame, focus)
        comparison_for_user(user, db, goal.baseline_id, retest.id, baseline_frame, retest_frame,
                            changes.get("same_setup", goal.same_setup))
    elif {"focus_joint", "baseline_frame"} & changes.keys():
        if goal.baseline is None:
            raise HTTPException(409, "The baseline was deleted. Create a new goal with an available baseline.")
        baseline_frame = _measured_joint(goal.baseline, baseline_frame, focus)
    if changes.get("status") == "completed" and (goal.baseline is None or retest is None):
        raise HTTPException(400, "Attach an available retest before marking this goal complete.")
    if retest_id is None:
        retest_frame = None
    for key in ("title", "notes", "focus_joint", "target_deg", "due_date", "status"):
        if key in changes:
            setattr(goal, key, changes[key])
    goal.retest = retest
    goal.baseline_frame = baseline_frame
    goal.retest_frame = retest_frame
    if {"baseline_frame", "retest_id", "retest_frame"} & changes.keys():
        goal.same_setup = bool(changes.get("same_setup", False)) if retest is not None else False
    elif "same_setup" in changes:
        goal.same_setup = bool(changes["same_setup"]) if retest is not None else False
    goal.updated_at = now()
    db.commit()
    return goal_out(goal)


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_goal(goal_id, user, db))
    db.commit()
