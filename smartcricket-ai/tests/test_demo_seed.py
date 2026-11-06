"""Future demo copies must identify synthetic activity and preserve their source."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.models import Analysis, Media
from scripts import seed_demo


def test_copied_analysis_has_demo_label_and_provenance_without_changing_source(monkeypatch):
    measured_at = datetime(2026, 10, 20, tzinfo=timezone.utc)
    original_summary = {"detected": True, "visible": 30, "quality": {"score": 0.9}}
    source = Analysis(id=7, media=Media(type="image", original_name="batter.jpg", file_path="source.jpg"),
                      mode="image", model="pose", summary=deepcopy(original_summary),
                      angles={"left_knee": {"deg": 142}}, confidence=0.8, latency_ms=1200,
                      created_at=measured_at, messages=[])
    saved = []
    db = SimpleNamespace(add_all=saved.extend, flush=lambda: None)
    monkeypatch.setattr(seed_demo, "copy_path", lambda *_args: "demo-copy.jpg")
    copy = seed_demo.clone_analysis(db, SimpleNamespace(id=42), source,
                                    measured_at + timedelta(days=1), "Morning nets")
    assert copy.media.session_label == "Demo · Morning nets"
    assert copy.summary["detected"] is True
    assert copy.summary["demo_provenance"]["synthetic_activity"] is True
    assert copy.summary["demo_provenance"]["source_analysis_id"] == source.id
    assert copy.summary["demo_provenance"]["source_created_at"] == measured_at.isoformat()
    assert copy.summary["demo_provenance"]["synthetic_latency"] is True
    assert copy.angles == source.angles and copy.confidence == source.confidence
    assert source.summary == original_summary and source.created_at == measured_at
