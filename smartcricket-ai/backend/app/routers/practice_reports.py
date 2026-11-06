"""Authenticated PDF download for a player's baseline and retest."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import User
from ..practice_report import comparison_pdf
from .analyses import owned_analysis
from .practice import comparison_for_user, goal_out, owned_goal

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.get("/compare/pdf")
def download_comparison(baseline_id: int = Query(gt=0), retest_id: int = Query(gt=0),
                        baseline_frame: int | None = Query(default=None, ge=0),
                        retest_frame: int | None = Query(default=None, ge=0), same_setup: bool = False,
                        goal_id: int | None = Query(default=None, gt=0),
                        user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = comparison_for_user(user, db, baseline_id, retest_id, baseline_frame, retest_frame, same_setup)
    goal = None
    if goal_id is not None:
        row = owned_goal(goal_id, user, db)
        if row.baseline_id != baseline_id:
            raise HTTPException(400, "This goal uses a different baseline. Open the goal's saved comparison.")
        goal = goal_out(row)
    pdf = comparison_pdf(data, owned_analysis(baseline_id, user, db), owned_analysis(retest_id, user, db), goal)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="SmartCricket_comparison_{baseline_id}_{retest_id}.pdf"',
        "Cache-Control": "no-store",
    })
