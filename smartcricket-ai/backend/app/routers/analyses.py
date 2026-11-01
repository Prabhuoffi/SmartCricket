"""History, single analysis, file access and deletion (FR-15, NFR-5)."""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Analysis, Media, User
from ..serialize import analysis_out

router = APIRouter(prefix="/api", tags=["analyses"])


def owned_analysis(analysis_id: int, user: User, db: Session) -> Analysis:
    """Return the analysis only if it belongs to the user; otherwise 404, so other users' IDs are not revealed."""
    a = db.scalar(select(Analysis).join(Media).where(Analysis.id == analysis_id, Media.user_id == user.id))
    if a is None:
        raise HTTPException(404, "Analysis not found")
    return a


@router.get("/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).join(Media).where(Media.user_id == user.id)
                      .order_by(Analysis.created_at.desc())).all()
    return [analysis_out(a, brief=True) for a in rows]


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return analysis_out(owned_analysis(analysis_id, user, db), with_messages=True)


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = owned_analysis(analysis_id, user, db)
    media = a.media
    paths = [a.output_path, media.file_path]
    db.delete(media)  # cascades to analyses and coach messages
    db.commit()
    for p in paths:
        if p and Path(p).is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p:
            Path(p).unlink(missing_ok=True)


@router.get("/files/{analysis_id}/{kind}")
def get_file(analysis_id: int, kind: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = owned_analysis(analysis_id, user, db)
    output = a.output_path
    if a.mode == "video" and output:
        output = str(Path(output) / "thumb.jpg")
    path = {"original": a.media.file_path, "output": output}.get(kind)
    if not path or not Path(path).exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.get("/files/{analysis_id}/{kind}/{t}")
def get_frame(analysis_id: int, kind: str, t: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Video frames: kind is 'frame' (plain), 'heat' (Grad-CAM overlay) or 'skel' (body skeleton), t is 0..14."""
    a = owned_analysis(analysis_id, user, db)
    if a.mode != "video" or kind not in ("frame", "heat", "skel") or not 0 <= t < 64:
        raise HTTPException(404, "File not found")
    path = Path(a.output_path) / f"{kind}_{t:02d}.jpg"
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)
