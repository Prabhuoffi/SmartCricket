"""POST /api/image/analyse: photo upload to posture report (FR-3, FR-4, FR-5)."""
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..models import Analysis, Media, User
from ..pose import pose_service
from ..serialize import analysis_out
from ..storage import save_upload

router = APIRouter(prefix="/api/image", tags=["image"])
log = logging.getLogger("smartcricket")


@router.post("/analyse")
async def analyse_image(file: UploadFile, session_label: str | None = Form(None),
                        user: User = Depends(current_user), db: Session = Depends(get_db)):
    path = await save_upload(file, "image")
    out_path = settings.output_dir / f"{uuid.uuid4().hex}_pose.jpg"
    try:
        t0 = time.perf_counter()
        report = await run_in_threadpool(pose_service.analyse_image, path, out_path)
        latency = int((time.perf_counter() - t0) * 1000)
        media = Media(user_id=user.id, type="image", file_path=str(path), original_name=file.filename or "",
                      session_label=session_label or None)
        analysis = Analysis(media=media, mode="image", model="mediapipe-pose-heavy",
                            angles=report["angles"], summary=report, output_path=str(out_path),
                            uncertain=not report["detected"], latency_ms=latency)
        db.add_all([media, analysis])
        db.commit()
    except Exception:
        db.rollback()
        log.exception("image analysis failed upload=%s", path.name)
        path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)
        raise HTTPException(500, "Analysis failed, please try again")
    return analysis_out(analysis)
