"""Dashboard numbers and chart data (FR-16)."""
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Analysis, Media, User

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).join(Media).where(Media.user_id == user.id)
                      .order_by(Analysis.created_at)).all()
    videos = [a for a in rows if a.mode == "video" and a.shot]
    images = [a for a in rows if a.mode == "image"]
    shots = Counter(a.shot for a in videos)
    confs = [a.confidence for a in videos if a.confidence is not None]
    knee = []  # front-knee trend from photos: the more bent of the two measured knees
    for a in images:
        vals = [v["deg"] for k, v in (a.angles or {}).items() if k.endswith("knee") and v["deg"] is not None]
        if vals:
            knee.append({"date": a.created_at.date().isoformat(), "deg": min(vals)})
    return {
        "total": len(rows),
        "images": len(images),
        "videos": sum(1 for a in rows if a.mode == "video"),
        "avg_confidence": round(sum(confs) / len(confs), 3) if confs else None,
        "top_shot": shots.most_common(1)[0][0] if shots else None,
        "shot_mix": [{"shot": s, "count": n} for s, n in shots.most_common()],
        "confidence_trend": [{"date": a.created_at.date().isoformat(), "confidence": a.confidence} for a in videos],
        "knee_trend": knee,
        "avg_visible": round(sum(a.summary.get("visible", 0) for a in images) / len(images), 1) if images else None,
    }
