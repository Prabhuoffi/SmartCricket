"""Player-owned read-only practice insights and matching CSV export."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import current_player
from ..db import get_db
from ..models import User
from ..practice_insights import build_insights, insights_csv

router = APIRouter(prefix="/api/insights", tags=["insights"])
Joint = Literal["left_elbow", "right_elbow", "left_knee", "right_knee", "left_hip", "right_hip", "left_shoulder", "right_shoulder"]


def filters(days: Literal[7, 14, 30] = 14, joint: Joint = "left_knee", include_demo: bool = False):
    return {"days": days, "joint": joint, "include_demo": include_demo}


@router.get("")
def insights(options: dict = Depends(filters), user: User = Depends(current_player), db: Session = Depends(get_db)):
    return build_insights(db, user.id, **options)


@router.get("/export.csv")
def export(options: dict = Depends(filters), user: User = Depends(current_player), db: Session = Depends(get_db)):
    data = build_insights(db, user.id, **options)
    return Response(insights_csv(data), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="SmartCricket_practice_insights.csv"',
                             "Cache-Control": "no-store"})
