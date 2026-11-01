"""Administrator features (FR-18): reference clips, model results, user list."""
import json
import logging
import shutil
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from training.sc_common import CLASSES

from ..auth import current_admin, current_user
from ..config import settings
from .. import trainer
from ..db import get_db
from ..models import Analysis, Media, ModelEvaluation, ReferenceClip, User
from ..storage import save_upload
from ..video import LABELS, video_service
from .video import reference_out

router = APIRouter(prefix="/api", tags=["admin"])
log = logging.getLogger("smartcricket")


@router.get("/models")
def models(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """Installed models and their stored test results (model comparison page)."""
    evals = db.scalars(select(ModelEvaluation).order_by(ModelEvaluation.id)).all()
    return {
        "installed": video_service.available(),
        "classes": CLASSES,
        "evaluations": [{"model": e.model_name, "label": LABELS.get(e.model_name, e.model_name),
                         "accuracy": e.accuracy, "macro_f1": e.macro_f1, "precision": e.precision, "recall": e.recall,
                         "ece_before": e.ece_before, "ece_after": e.ece_after, "ms_per_clip": e.ms_per_clip,
                         "evaluated_at": e.evaluated_at.isoformat()} for e in evals],
    }


@router.post("/admin/evaluations")
async def import_evaluations(file: UploadFile, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Import results/summary.json written by the training notebook (mean over seeds per model)."""
    try:
        data = json.loads(await file.read())
        rows = data["results"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, "This is not a summary.json file from the training notebook")
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    mean = lambda rs, k: sum(float(r[k]) for r in rs) / len(rs)
    db.execute(delete(ModelEvaluation))
    for m, rs in by_model.items():
        db.add(ModelEvaluation(model_name=m, accuracy=mean(rs, "top1"), macro_f1=mean(rs, "macro_f1"),
                               precision=mean(rs, "precision"), recall=mean(rs, "recall"),
                               ece_before=mean(rs, "ece_before"), ece_after=mean(rs, "ece_after")))
    db.commit()
    return {"imported": {m: len(rs) for m, rs in by_model.items()}}


@router.post("/admin/references", status_code=201)
async def add_reference(file: UploadFile, shot: str = Form(...), label: str | None = Form(None),
                        admin: User = Depends(current_admin), db: Session = Depends(get_db)):
    if shot not in CLASSES:
        raise HTTPException(400, "Unknown shot type")
    path = await save_upload(file, "video")
    out_dir = settings.output_dir / f"ref_{uuid.uuid4().hex}"
    try:
        res = await run_in_threadpool(video_service.reference_angles, path, out_dir)
    except Exception:
        log.exception("reference processing failed")
        path.unlink(missing_ok=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(422, "The clip could not be processed")
    seen = sum(1 for f in res["angles"] for v in f.values() if v is not None)
    if seen == 0:
        path.unlink(missing_ok=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(422, "No body was detected in this clip, so it cannot be used as a reference")
    ref = ReferenceClip(shot=shot, file_path=str(path), added_by=admin.id,
                        angles={"seq": res["angles"], "landmarks": res["landmarks"], "dir": str(out_dir),
                                "label": (label or "").strip() or f"{shot} reference"})
    db.add(ref)
    db.commit()
    return reference_out(ref)


@router.delete("/admin/references/{ref_id}", status_code=204)
def delete_reference(ref_id: int, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    ref = db.get(ReferenceClip, ref_id)
    if ref is None:
        raise HTTPException(404, "Reference clip not found")
    for a in db.scalars(select(Analysis).where(Analysis.reference_id == ref_id)):
        a.reference_id = None
    paths = (ref.file_path, ref.angles.get("dir"))
    db.delete(ref)
    db.commit()
    Path(paths[0]).unlink(missing_ok=True)
    if paths[1]:
        shutil.rmtree(paths[1], ignore_errors=True)


@router.get("/admin/users")
def users(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Media.user_id, func.count(Analysis.id)).join(Analysis).group_by(Media.user_id)).all())
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "created_at": u.created_at.isoformat(),
             "analyses": counts.get(u.id, 0)} for u in db.scalars(select(User).order_by(User.id)).all()]


@router.get("/admin/overview")
def overview(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    """Usage across all players for the admin Players dashboard. Numbers only: no photos or videos of other users."""
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    aware = lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # SQLite returns naive UTC times
    now = datetime.now(timezone.utc)
    week_ago, start = now - timedelta(days=7), (now - timedelta(days=13)).date()
    users = db.scalars(select(User).where(User.role == "player").order_by(User.id)).all()
    ids = [u.id for u in users]
    rows = db.execute(select(Analysis, Media.user_id).join(Media).where(Media.user_id.in_(ids))
                      .order_by(Analysis.created_at.desc())).all()

    per_user = {u.id: {"photos": 0, "videos": 0, "last": None, "visible": [], "shots": Counter()} for u in users}
    daily = Counter()
    for a, uid in rows:
        st = per_user.setdefault(uid, {"photos": 0, "videos": 0, "last": None, "visible": [], "shots": Counter()})
        st["photos" if a.mode == "image" else "videos"] += 1
        st["last"] = st["last"] or a.created_at
        if a.mode == "image" and (a.summary or {}).get("visible") is not None:
            st["visible"].append(a.summary["visible"])
        if a.shot:
            st["shots"][a.shot] += 1
        d = a.created_at.astimezone(timezone.utc).date()
        if d >= start:
            daily[d.isoformat()] += 1

    names = {u.id: u.name for u in users}
    players = [{
        "id": u.id, "name": u.name, "email": u.email, "role": u.role, "joined": u.created_at.isoformat(),
        "photos": per_user[u.id]["photos"], "videos": per_user[u.id]["videos"],
        "analyses": per_user[u.id]["photos"] + per_user[u.id]["videos"],
        "last_active": per_user[u.id]["last"].isoformat() if per_user[u.id]["last"] else None,
        "avg_visible": round(sum(per_user[u.id]["visible"]) / len(per_user[u.id]["visible"]), 1) if per_user[u.id]["visible"] else None,
        "top_shot": per_user[u.id]["shots"].most_common(1)[0][0] if per_user[u.id]["shots"] else None,
    } | trainer.snapshot(u, db) for u in users]
    return {
        "totals": {
            "players": len(users),
            "active_week": sum(1 for u in users if per_user[u.id]["last"] and aware(per_user[u.id]["last"]) >= week_ago),
            "analyses": len(rows),
            "photos": sum(p["photos"] for p in players),
            "videos": sum(p["videos"] for p in players),
        },
        "daily": [{"date": (start + timedelta(days=i)).isoformat(), "count": daily.get((start + timedelta(days=i)).isoformat(), 0)}
                  for i in range(14)],
        "players": players,
        "setup": {"models_installed": len(video_service.available()),
                  "results_imported": db.scalar(select(func.count(ModelEvaluation.id))) > 0,
                  "reference_clips": db.scalar(select(func.count(ReferenceClip.id))),
                  "admins": db.scalar(select(func.count(User.id)).where(User.role == "admin"))},
        "recent": [{"player": names.get(uid, "Unknown"), "mode": a.mode, "shot": a.shot,
                    "visible": (a.summary or {}).get("visible"), "label": a.media.session_label or a.media.original_name,
                    "at": a.created_at.isoformat()} for a, uid in rows[:8]],
    }
