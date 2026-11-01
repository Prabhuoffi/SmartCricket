"""Video analysis, reference comparison and reference clip frames (FR-6 to FR-13)."""
import logging
import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import dtw
from ..auth import current_player, current_user
from ..config import settings
from ..db import get_db
from ..models import Analysis, Media, ReferenceClip, User
from ..serialize import analysis_out
from ..storage import save_upload
from ..video import KINDS, LABELS, LONG_VIDEO_S, MOVEMENT, cut_clip, find_shots, video_info, video_service
from .analyses import owned_analysis

router = APIRouter(prefix="/api", tags=["video"])
log = logging.getLogger("smartcricket")


@router.get("/video/status")
def status(_: User = Depends(current_player)):
    """Movement analysis always works; trained shot classifiers are listed when installed."""
    trained = video_service.available()
    models = trained + [{"kind": MOVEMENT, "label": LABELS[MOVEMENT]}]
    return {"ready": True, "shot_models": bool(trained), "models": models, "default": models[0]["kind"]}


@router.post("/video/analyse")
async def analyse_video(file: UploadFile, model: str | None = Form(None), session_label: str | None = Form(None),
                        user: User = Depends(current_player), db: Session = Depends(get_db)):
    if model is None:  # best installed shot model, otherwise movement analysis
        model = next((m["kind"] for m in video_service.available()), MOVEMENT)
    if model not in KINDS and model != MOVEMENT:
        raise HTTPException(400, f"Unknown model '{model}'")
    if model != MOVEMENT and not (settings.model_dir / f"{model}.pt").exists():
        raise HTTPException(503, "This model is not installed yet. Train it in Colab and copy the .pt file into models/")
    path = await save_upload(file, "video")
    name, label = file.filename or "", session_label or None
    try:
        n, fps, _, _ = video_info(path)
        long_video = n / (fps or 25) > LONG_VIDEO_S
        shots = await run_in_threadpool(find_shots, video_service, path) if long_video else []
    except Exception:
        long_video, shots = False, []
    if not shots:   # one stroke (or no clear shots found): analyse the whole clip
        return analysis_out(await _analyse_one(path, model, user, db, name, label))

    # A practice video with several shots: cut each shot into its own clip and analyse it on its own.
    results = []
    try:
        for k, s in enumerate(shots, 1):
            clip = path.with_name(f"{path.stem}_shot{k}.mp4")
            await run_in_threadpool(cut_clip, path, s["start_s"], s["end_s"], clip)
            a = await _analyse_one(clip, model, user, db, f"{name} · shot {k} at {s['peak_s']:.1f} s",
                                   f"{label} · shot {k}" if label else f"Shot {k} of {len(shots)}")
            results.append(analysis_out(a, brief=True))
    finally:
        path.unlink(missing_ok=True)   # the shot clips are kept; the long original is not needed any more
    return {"multi": True, "count": len(results), "duration_s": round(n / fps, 1),
            "shots": [{"start_s": round(s["start_s"], 2), "end_s": round(s["end_s"], 2), "peak_s": round(s["peak_s"], 2)} for s in shots],
            "analyses": results}


async def _analyse_one(path, model, user, db, original_name, session_label):
    out_dir = settings.output_dir / uuid.uuid4().hex
    try:
        t0 = time.perf_counter()
        result = await run_in_threadpool(video_service.analyse, path, model, out_dir)
        latency = int((time.perf_counter() - t0) * 1000)
        media = Media(user_id=user.id, type="video", file_path=str(path), original_name=original_name,
                      session_label=session_label)
        analysis = Analysis(media=media, mode="video", model=model, shot=result["shot"],
                            confidence=result["confidence"], uncertain=result["uncertain"], top3=result["top3"],
                            attention=result["attention"], summary=result, output_path=str(out_dir),
                            latency_ms=latency)
        db.add_all([media, analysis])
        db.commit()
        return analysis
    except HTTPException:
        raise
    except ValueError as e:  # unreadable video found while sampling frames
        path.unlink(missing_ok=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(422, str(e))
    except Exception:
        db.rollback()
        log.exception("video analysis failed upload=%s", path.name)
        path.unlink(missing_ok=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(500, "Analysis failed, please try again")


@router.post("/video/recognise")
async def recognise(frames: list[UploadFile], model: str | None = Form(None), user: User = Depends(current_player)):
    """Live shot recognition: 15 camera frames of one stroke from the Live mirror page -> shot and confidence.
    The frames are put through the same pipeline as an uploaded clip, then deleted; nothing is stored."""
    import tempfile
    import cv2
    import numpy as np
    installed = [m["kind"] for m in video_service.available()]
    if not installed:
        raise HTTPException(503, "Shot recognition switches on when the trained shot models are installed")
    model = model if model in installed else installed[0]
    if not 8 <= len(frames) <= 32:
        raise HTTPException(422, "Send between 8 and 32 frames of one stroke")
    imgs = []
    for f in frames:
        data = await f.read()
        if len(data) > 3_000_000:
            raise HTTPException(413, "A frame is too large")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(422, "A frame could not be read")
        imgs.append(img)
    h, w = imgs[0].shape[:2]
    work = Path(tempfile.mkdtemp(prefix="sc_live_"))
    try:
        clip = work / "stroke.mp4"
        out = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
        for img in imgs:
            out.write(cv2.resize(img, (w, h)))
        out.release()
        t0 = time.perf_counter()
        r = await run_in_threadpool(video_service.analyse, clip, model, work / "out")
        return {"shot": r["shot"], "confidence": r["confidence"], "uncertain": r["uncertain"], "top3": r["top3"],
                "model": LABELS.get(model, model), "key_frame": r["key_frame"], "ms": int((time.perf_counter() - t0) * 1000)}
    finally:
        shutil.rmtree(work, ignore_errors=True)   # the frames never stay on the server


class CompareIn(BaseModel):
    reference_id: int


@router.post("/video/{analysis_id}/compare")
def compare(analysis_id: int, body: CompareIn, user: User = Depends(current_player), db: Session = Depends(get_db)):
    a = owned_analysis(analysis_id, user, db)
    if a.mode != "video":
        raise HTTPException(400, "Comparison is only available for videos")
    ref = db.get(ReferenceClip, body.reference_id)
    if ref is None:
        raise HTTPException(404, "Reference clip not found")
    result = dtw.compare(a.summary["angles_seq"], ref.angles["seq"])
    result.update(reference_id=ref.id, reference_label=ref.angles.get("label") or ref.shot, reference_shot=ref.shot)
    a.reference_id, a.dtw = ref.id, result
    db.commit()
    return result


@router.get("/references")
def references(shot: str | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(ReferenceClip).order_by(ReferenceClip.shot, ReferenceClip.id)
    if shot:
        q = q.where(ReferenceClip.shot == shot)
    return [reference_out(r) for r in db.scalars(q).all()]


def reference_out(r: ReferenceClip) -> dict:
    return {"id": r.id, "shot": r.shot, "label": r.angles.get("label") or r.shot,
            "frames": len(r.angles.get("seq", [])), "thumb": f"/api/references/{r.id}/frame/7"}


@router.get("/references/{ref_id}/pose")
def reference_pose(ref_id: int, _: User = Depends(current_player), db: Session = Depends(get_db)):
    """The model player's movement for the live "shadow the pro" ghost: 15 frames of normalised landmarks
    (x/width, y/height, visibility) and joint angles."""
    r = db.get(ReferenceClip, ref_id)
    if r is None:
        raise HTTPException(404, "Reference clip not found")
    size = None
    first = Path(r.angles.get("dir", "")) / "frame_00.jpg"
    if first.exists():
        import cv2
        img = cv2.imread(str(first))
        size = [img.shape[1], img.shape[0]] if img is not None else None
    return {"id": r.id, "shot": r.shot, "label": r.angles.get("label") or r.shot, "frame_size": size,
            "landmarks": r.angles.get("landmarks") or [], "angles": r.angles.get("seq") or []}


@router.get("/references/{ref_id}/frame/{t}")
def reference_frame(ref_id: int, t: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(ReferenceClip, ref_id)
    if r is None:
        raise HTTPException(404, "Reference clip not found")
    p = Path(r.angles["dir"]) / f"frame_{t:02d}.jpg"
    if not p.exists():
        raise HTTPException(404, "Frame not found")
    return FileResponse(p)
