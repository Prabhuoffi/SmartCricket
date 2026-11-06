"""Player-owned baseline/retest measurements and saved practice-goal lifecycle."""
from datetime import datetime, timedelta, timezone
from itertools import count

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import settings
from backend.app.db import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import Analysis, Media, PracticeGoal, User
from backend.app.practice import JOINTS, PracticeError, capture_measurements, compare_analyses
from backend.app.routers.practice import GoalCreate, GoalUpdate

START = datetime(2026, 11, 4, 9, tzinfo=timezone.utc)


def capture(analysis_id=1, *, mode="image", day=0, angles=None, sequence=None, quality=True):
    values = {j: {"deg": 140.0, "visibility": .9} for j in JOINTS}
    values.update(angles or {})
    summary = {"detected": True}
    if quality:
        summary["quality"] = {"grade": "Good", "score": 88,
                              "checks": [{"key": "view", "label": "Side-on view", "level": "good"}]}
    if mode == "video":
        summary.update(angles_seq=sequence if sequence is not None else [{j: 130.0 for j in JOINTS}] * 3,
                       key_frame=1, frames=15, tracked_frames=3)
    media = Media(user_id=1, type=mode, file_path=str(settings.upload_dir / f"capture-{analysis_id}.jpg"),
                  original_name=f"Capture {analysis_id}")
    return Analysis(id=analysis_id, media=media, mode=mode, model="pose", angles=values, summary=summary,
                    uncertain=False, created_at=START + timedelta(days=day))


def test_photo_changes_only_include_shared_visible_joints():
    baseline = capture(angles={"left_knee": {"deg": 148, "visibility": .9},
                               "right_elbow": {"deg": 90, "visibility": .4}})
    retest = capture(2, day=1, angles={"left_knee": {"deg": 139, "visibility": .9}, "right_hip": {"deg": None}})
    result = compare_analyses(baseline, retest, same_setup=True)
    knee = next(r for r in result["rows"] if r["joint"] == "left_knee")
    assert knee == {"joint": "left_knee", "label": "Left knee", "baseline_deg": 148,
                    "retest_deg": 139, "change_deg": -9}
    assert result["common_joints"] == 6 and len(result["omitted"]) == 2
    assert result["comparable"] is True
    assert result["baseline"]["frame"] is None
    assert result["baseline"]["preview_url"] == "/api/practice/captures/1/preview"
    assert "does not establish better technique" in result["note"]


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), -1, 181, True, "130"])
def test_invalid_measurements_never_become_deltas(invalid):
    baseline, retest = capture(), capture(2, day=1)
    baseline.angles["left_knee"] = {"deg": invalid, "visibility": .9}
    result = compare_analyses(baseline, retest)
    assert not any(r["joint"] == "left_knee" for r in result["rows"])
    assert any(r["joint"] == "left_knee" for r in result["omitted"])


@pytest.mark.parametrize("visibility", [float("nan"), float("inf"), "clear", False, .2, 1.1])
def test_invalid_or_low_visibility_is_not_compared(visibility):
    baseline = capture(angles={"left_knee": {"deg": 120, "visibility": visibility}})
    assert capture_measurements(baseline)[0]["left_knee"] is None


def test_zero_degrees_is_a_measurement_and_missing_person_is_not():
    a = capture(angles={"left_knee": {"deg": 0, "visibility": .9}})
    assert capture_measurements(a)[0]["left_knee"] == 0
    a.summary["detected"] = False
    assert all(value is None for value in capture_measurements(a)[0].values())


def test_no_shared_joints_is_an_error_not_a_zero_change():
    a, b = capture(), capture(2, day=1)
    b.angles = {}
    with pytest.raises(PracticeError, match="No joint"):
        compare_analyses(a, b)


def test_exploratory_comparison_requires_capture_checks_even_after_confirmation():
    a, b = capture(), capture(2, day=1)
    assert not compare_analyses(a, b)["comparable"]
    b.summary["quality"]["checks"][0]["label"] = "Front-on view"
    assert not compare_analyses(a, b, same_setup=True)["comparable"]
    b.summary.pop("quality")
    result = compare_analyses(a, b, same_setup=True)
    assert not result["comparable"] and result["retest"]["quality"] == {"grade": None, "score": None}
    assert "exploratory" in result["note"]


def test_small_shared_set_or_conflicting_confident_shots_stays_exploratory():
    a, b = capture(), capture(2, day=1)
    b.angles = {"left_knee": {"deg": 140, "visibility": .9}}
    assert not compare_analyses(a, b, same_setup=True)["comparable"]
    b = capture(2, day=1)
    a.shot, b.shot = "Cover Drive", "Pull"
    assert not compare_analyses(a, b, same_setup=True)["comparable"]
    b.uncertain = True
    assert compare_analyses(a, b, same_setup=True)["comparable"]


def test_video_uses_selected_frames_and_actual_stored_frame_count():
    a = capture(mode="video", sequence=[{j: 100 for j in JOINTS}, {j: 120 for j in JOINTS}])
    b = capture(2, mode="video", day=1, sequence=[{j: 140 for j in JOINTS}, {j: 150 for j in JOINTS}])
    result = compare_analyses(a, b, 0, 1, True)
    assert result["baseline"]["frames"] == 2  # summary.frames intentionally says 15
    assert result["baseline"]["frame"] == 0 and result["retest"]["frame"] == 1
    assert result["baseline"]["preview_url"] == "/api/practice/captures/1/preview?frame=0"
    assert all(r["change_deg"] == 50 for r in result["rows"])
    assert capture_measurements(a)[1] == 1  # key frame is the default only


@pytest.mark.parametrize("frame", [-1, 2, True])
def test_invalid_selected_video_frame_rejected(frame):
    with pytest.raises(PracticeError, match="between"):
        capture_measurements(capture(mode="video", sequence=[{}, {}]), frame)


def test_photo_frames_unsupported_and_video_without_sequence_needs_reanalysis():
    with pytest.raises(PracticeError, match="Photos"):
        capture_measurements(capture(), 0)
    with pytest.raises(PracticeError, match="no stored joint frames"):
        capture_measurements(capture(mode="video", sequence=[]))


@pytest.mark.parametrize("baseline,retest,message", [
    (capture(), capture(), "different captures"),
    (capture(), capture(2, mode="video", day=1), "Mixed"),
    (capture(day=1), capture(2), "on or after"),
])
def test_pair_identity_mode_and_chronology_rules(baseline, retest, message):
    with pytest.raises(PracticeError, match=message):
        compare_analyses(baseline, retest)


def test_input_models_reject_blank_titles_and_nonfinite_targets():
    with pytest.raises(ValidationError):
        GoalCreate(title="  ", baseline_id=1, focus_joint="left_knee")
    with pytest.raises(ValidationError):
        GoalUpdate(target_deg=float("nan"))
    with pytest.raises(ValidationError):
        GoalUpdate(focus_joint=None)


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine)


accounts = count()


def player(client):
    response = client.post("/api/auth/register", json={"name": "Practice player", "password": "password123",
                                                       "email": f"practice{next(accounts)}@example.com"})
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    return headers, user_id


def save_capture(user_id, **kwargs):
    a = capture(**kwargs)
    a.id = None
    a.media.user_id = user_id
    with SessionLocal() as db:
        db.add(a)
        db.commit()
        return a.id


def test_classified_clip_preview_uses_saved_landmarks_when_no_skeleton_file_exists(client, tmp_path):
    import cv2
    import numpy as np

    headers, user_id = player(client)
    analysis_id = save_capture(user_id, mode="video")
    frame_dir = tmp_path / "classified"
    frame_dir.mkdir()
    cv2.imwrite(str(frame_dir / "frame_00.jpg"), np.full((120, 160, 3), 120, np.uint8))
    points = [[0, 0, 0] for _ in range(33)]
    points[11], points[12] = [.25, .5, 1], [.75, .5, 1]
    with SessionLocal() as db:
        row = db.get(Analysis, analysis_id)
        row.model, row.shot, row.output_path = "fusion", "Cover Drive", str(frame_dir)
        row.summary = {**row.summary, "landmarks": [points, points, points]}
        db.commit()
    response = client.get(f"/api/practice/captures/{analysis_id}/preview?frame=0", headers=headers)
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    assert image.shape == (120, 160, 3)
    assert np.max(np.abs(image[60, 80].astype(int) - 120)) > 30  # visible tracked shoulder line
    assert [path.name for path in frame_dir.iterdir()] == ["frame_00.jpg"]  # no inference/output mutation
    other, _ = player(client)
    assert client.get(f"/api/practice/captures/{analysis_id}/preview?frame=0", headers=other).status_code == 404
    assert client.get(f"/api/practice/captures/{analysis_id}/preview?frame=63", headers=headers).status_code == 400


def test_preview_missing_file_and_photo_frame_have_explicit_errors(client):
    headers, user_id = player(client)
    analysis_id = save_capture(user_id)
    assert client.get(f"/api/practice/captures/{analysis_id}/preview", headers=headers).status_code == 404
    assert client.get(f"/api/practice/captures/{analysis_id}/preview?frame=0", headers=headers).status_code == 400


def test_api_requires_player_session(client):
    assert client.get("/api/practice/goals").status_code == 401
    h, uid = player(client)
    with SessionLocal() as db:
        db.get(User, uid).role = "admin"
        db.commit()
    assert client.get("/api/practice/goals", headers=h).status_code == 403


def test_goals_lifecycle_target_and_manual_completion(client):
    h, uid = player(client)
    baseline = save_capture(uid)
    retest = save_capture(uid, day=1, angles={"left_knee": {"deg": 130, "visibility": .9}})
    created = client.post("/api/practice/goals", headers=h, json={"title": "  Work on knee position  ",
                          "baseline_id": baseline, "focus_joint": "left_knee", "target_deg": 135,
                          "notes": "Compare the same drive", "due_date": "2026-11-20"})
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["title"] == "Work on knee position" and goal["status"] == "active"
    assert goal["baseline"]["id"] == baseline and goal["baseline_frame"] is None
    url = f"/api/practice/goals/{goal['id']}"
    assert client.patch(url, headers=h, json={"status": "completed"}).status_code == 400
    response = client.patch(url, headers=h, json={"retest_id": retest, "same_setup": True, "status": "completed"})
    assert response.status_code == 200, response.text
    assert response.json()["retest"]["id"] == retest and response.json()["same_setup"] is True
    assert response.json()["status"] == "completed"  # chosen by the player, never inferred from an angle
    response = client.patch(url, headers=h, json={"target_deg": None, "due_date": None, "status": "active"})
    assert response.status_code == 200 and response.json()["target_deg"] is None
    listing = client.get("/api/practice/goals", headers=h).json()
    assert listing["active_count"] == 1 and len(listing["joints"]) == 8
    assert client.delete(url, headers=h).status_code == 204
    assert client.get("/api/practice/goals", headers=h).json()["goals"] == []


def test_foreign_analyses_and_goals_are_not_disclosed(client):
    h, uid = player(client)
    other, other_uid = player(client)
    baseline, retest = save_capture(uid), save_capture(uid, day=1)
    goal = client.post("/api/practice/goals", headers=h,
                       json={"title": "My goal", "baseline_id": baseline, "focus_joint": "left_knee"}).json()
    assert client.get("/api/practice/goals", headers=other).json()["goals"] == []
    assert client.post("/api/practice/goals", headers=other,
                        json={"title": "No access", "baseline_id": baseline, "focus_joint": "left_knee"}).status_code == 404
    assert client.get(f"/api/practice/compare?baseline_id={baseline}&retest_id={retest}", headers=other).status_code == 404
    url = f"/api/practice/goals/{goal['id']}"
    assert client.patch(url, headers=other, json={"notes": "No access"}).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    foreign_retest = save_capture(other_uid, day=1)
    assert client.patch(url, headers=h, json={"retest_id": foreign_retest}).status_code == 404


def test_goal_focus_visibility_and_retest_eligibility(client):
    h, uid = player(client)
    baseline = save_capture(uid, angles={"left_knee": {"deg": None}})
    body = {"title": "Visible goal", "baseline_id": baseline, "focus_joint": "left_knee"}
    assert client.post("/api/practice/goals", headers=h, json=body).status_code == 400
    body["focus_joint"] = "right_knee"
    goal = client.post("/api/practice/goals", headers=h, json=body).json()
    url = f"/api/practice/goals/{goal['id']}"
    mixed = save_capture(uid, mode="video", day=1)
    assert client.patch(url, headers=h, json={"retest_id": mixed}).status_code == 400
    assert client.patch(url, headers=h, json={"retest_id": baseline}).status_code == 400
    assert client.patch(url, headers=h, json={"focus_joint": "left_knee"}).status_code == 400


def test_video_goal_remembers_both_selected_frames(client):
    h, uid = player(client)
    baseline = save_capture(uid, mode="video", sequence=[{j: 100 for j in JOINTS}, {j: 130 for j in JOINTS}])
    retest = save_capture(uid, mode="video", day=1, sequence=[{j: 140 for j in JOINTS}, {j: 160 for j in JOINTS}])
    goal = client.post("/api/practice/goals", headers=h, json={"title": "Match phase", "baseline_id": baseline,
                       "baseline_frame": 0, "focus_joint": "left_knee"}).json()
    response = client.patch(f"/api/practice/goals/{goal['id']}", headers=h,
                            json={"baseline_frame": 1, "retest_id": retest, "retest_frame": 0, "same_setup": True})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["baseline_frame"] == 1 and saved["retest_frame"] == 0
    result = client.get(f"/api/practice/compare?baseline_id={baseline}&retest_id={retest}&baseline_frame=1&retest_frame=0&same_setup=true",
                        headers=h)
    assert result.status_code == 200 and all(row["change_deg"] == 10 for row in result.json()["rows"])
    response = client.patch(f"/api/practice/goals/{goal['id']}", headers=h, json={"baseline_frame": 0})
    assert response.status_code == 200 and response.json()["same_setup"] is False
    response = client.patch(f"/api/practice/goals/{goal['id']}", headers=h,
                            json={"baseline_frame": 1, "same_setup": True})
    assert response.status_code == 200 and response.json()["same_setup"] is True


@pytest.mark.parametrize("side", ["baseline", "retest"])
def test_deleting_evidence_preserves_goal_and_detaches_capture(client, side):
    h, uid = player(client)
    baseline, retest = save_capture(uid), save_capture(uid, day=1)
    goal = client.post("/api/practice/goals", headers=h,
                       json={"title": "Keep my notes", "baseline_id": baseline, "focus_joint": "left_knee"}).json()
    url = f"/api/practice/goals/{goal['id']}"
    assert client.patch(url, headers=h, json={"retest_id": retest, "same_setup": True,
                                             "status": "completed"}).status_code == 200
    capture_id = baseline if side == "baseline" else retest
    assert client.delete(f"/api/analyses/{capture_id}", headers=h).status_code == 204
    saved = client.get("/api/practice/goals", headers=h).json()["goals"][0]
    assert saved[side] is None and saved[f"{side}_frame"] is None and saved["same_setup"] is False
    assert saved["status"] == "completed"  # preserve user-marked history when source media is removed
    assert client.patch(url, headers=h, json={"notes": "Source removed", "status": "archived"}).status_code == 200
    assert client.patch(url, headers=h, json={"status": "completed"}).status_code in (400, 409)
