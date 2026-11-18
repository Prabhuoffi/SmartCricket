"""Reference frames remain usable when the project folder moves."""
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.auth import make_token
from backend.app.config import settings
from backend.app.db import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import ReferenceClip, User


def test_reference_frame_and_cleanup_use_current_project_folders(tmp_path, monkeypatch):
    output_dir = tmp_path / "current" / "outputs"
    upload_dir = tmp_path / "current" / "uploads"
    output_dir.mkdir(parents=True)
    upload_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "output_dir", output_dir)
    monkeypatch.setattr(settings, "upload_dir", upload_dir)
    frame_name = "ref_" + "a" * 32
    frame_dir = output_dir / frame_name
    frame_dir.mkdir()
    ok, encoded = cv2.imencode(".jpg", np.full((12, 20, 3), 180, np.uint8))
    assert ok
    (frame_dir / "frame_00.jpg").write_bytes(encoded.tobytes())
    clip_name = "b" * 32 + ".mp4"
    (upload_dir / clip_name).write_bytes(b"test clip")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        player = User(name="Player", email="reference-player@example.com", role="player", password_hash="unused")
        admin = User(name="Admin", email="reference-admin@example.com", role="admin", password_hash="unused")
        db.add_all([player, admin])
        db.flush()
        ref = ReferenceClip(shot="Cover Drive", file_path=str(Path("/old/project/uploads") / clip_name),
                            angles={"dir": str(Path("/old/project/outputs") / frame_name), "seq": [{}]},
                            added_by=admin.id)
        db.add(ref)
        db.commit()
        ref_id = ref.id
        player_headers = {"Authorization": f"Bearer {make_token(player.id)}"}
        admin_headers = {"Authorization": f"Bearer {make_token(admin.id)}"}

    with TestClient(app) as client:
        frame = client.get(f"/api/references/{ref_id}/frame/0", headers=admin_headers)
        assert frame.status_code == 200 and frame.content == encoded.tobytes()
        pose = client.get(f"/api/references/{ref_id}/pose", headers=player_headers)
        assert pose.status_code == 200 and pose.json()["frame_size"] == [20, 12]
        assert client.get(f"/api/references/{ref_id}/frame/1", headers=admin_headers).status_code == 404
        assert client.delete(f"/api/admin/references/{ref_id}", headers=admin_headers).status_code == 204

    assert not frame_dir.exists()
    assert not (upload_dir / clip_name).exists()
    Base.metadata.drop_all(engine)
