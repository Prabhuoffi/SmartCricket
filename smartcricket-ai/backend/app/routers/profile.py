"""Only the signed-in player can read or save their stated capture preferences."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import current_player
from ..db import get_db
from ..models import PlayerProfile, User, now
from ..player_profile import profile_out

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handedness: Literal["unspecified", "right", "left"] = "unspecified"
    experience: Literal["unspecified", "beginner", "regular", "experienced"] = "unspecified"
    camera_view: Literal["side-on", "front-on", "angled"] = "side-on"
    focus: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)

    @field_validator("focus", "notes", mode="before")
    @classmethod
    def clean_text(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.get("")
def get_profile(user: User = Depends(current_player), db: Session = Depends(get_db)):
    # Reading an unsaved profile must not create activity or preference records.
    return profile_out(db.get(PlayerProfile, user.id))


@router.put("")
def save_profile(body: ProfileInput, user: User = Depends(current_player), db: Session = Depends(get_db)):
    row = db.get(PlayerProfile, user.id)
    if row is None:
        row = PlayerProfile(user_id=user.id)
        db.add(row)
    values = body.model_dump()
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_at = now()
    try:
        db.commit()
    except IntegrityError:
        # Two first-time saves can race. Keep one row per player, then apply the
        # later request without leaking or rewriting another player's profile.
        db.rollback()
        row = db.get(PlayerProfile, user.id)
        if row is None:
            raise
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now()
        db.commit()
    return profile_out(row)
