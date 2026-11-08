import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth
from .config import settings
from .db import Base, engine
from .routers import (admin, analyses, coach, dashboard, feedback, image, insights, practice, practice_reports, profile,
                      reports, train, video)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")



@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="SmartCricket AI", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def revalidate_frontend(request, call_next):
    """Make browsers check for a newer copy of pages, styles and scripts on every load,
    so design changes show up without a hard refresh."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/app/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Player-only areas: an administrator account gets 403 here (Section 4.1, user classes).
for r in (image.router, analyses.router, dashboard.router, reports.router, coach.router, train.router,
          practice.router, practice_reports.router, profile.router, insights.router):
    app.include_router(r, dependencies=[Depends(auth.current_player)])
# Shared (mixed per endpoint) and admin areas.
for r in (auth.router, video.router, admin.router, feedback.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "coach_configured": bool(settings.llm_api_key)}


@app.get("/api/live/pose-model")
def live_pose_model(_: auth.User = Depends(auth.current_player)):
    """Serve the installed pose task to the browser without an external model download."""
    model = settings.model_dir / "pose_landmarker_full.task"
    if not model.is_file():
        raise HTTPException(503, "Live pose model is missing. Install pose_landmarker_full.task in models/.")
    return FileResponse(model, media_type="application/octet-stream")


# ---------------------------------------------------------------- phone mode (run_phone.py: https on the local Wi-Fi)
DATA = settings.output_dir.parent
PHONE_SCRIPT = DATA.parent / "run_phone.py"


def _lan_status() -> dict:
    import json
    import socket
    f = DATA / "lan.json"
    if not f.exists():
        return {"available": False}
    info = json.loads(f.read_text())
    try:
        socket.create_connection(("127.0.0.1", info["port"]), timeout=0.3).close()
        return {"available": True, "url": info["url"]}
    except OSError:
        return {"available": False, "url": info["url"]}


@app.get("/api/lan")
def lan(_: auth.User = Depends(auth.current_user)):
    """Address for phones on the same Wi-Fi, when phone mode is running."""
    return _lan_status()


@app.post("/api/lan/start")
def lan_start(_: auth.User = Depends(auth.current_user)):
    """Start phone mode from the Live page (same as running run_phone.py by hand)."""
    import subprocess
    import sys
    import time
    if _lan_status()["available"]:
        return _lan_status()
    log_file = open(DATA / "phone.log", "w")
    proc = subprocess.Popen([sys.executable, str(PHONE_SCRIPT)], cwd=str(PHONE_SCRIPT.parent), stdout=log_file,
                            stderr=subprocess.STDOUT, start_new_session=True)
    (DATA / "phone.pid").write_text(str(proc.pid))
    for _ in range(40):                      # wait up to 10 s for the https server to answer
        time.sleep(0.25)
        st = _lan_status()
        if st["available"]:
            return st
        if proc.poll() is not None:
            break
    raise HTTPException(500, "Phone mode could not start. See data/phone.log.")


@app.post("/api/lan/stop")
def lan_stop(_: auth.User = Depends(auth.current_user)):
    import os
    import signal
    pid_file = DATA / "phone.pid"
    if pid_file.exists():
        try:
            os.killpg(int(pid_file.read_text()), signal.SIGTERM)   # the script and its server
        except (ProcessLookupError, ValueError, PermissionError):
            pass
        pid_file.unlink(missing_ok=True)
    return {"available": False}


@app.get("/")
def landing():
    """The public landing page lives at the site root; the app pages stay under /app/."""
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(settings.frontend_dir / "img" / "favicon.svg", media_type="image/svg+xml")


app.mount("/app", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
