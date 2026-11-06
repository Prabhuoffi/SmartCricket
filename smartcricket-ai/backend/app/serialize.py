from datetime import datetime, timezone

from .models import Analysis


HEAVY = ("landmarks", "angles_seq", "edges", "world", "world_seq", "angles_3d_seq")


def timestamp(value: datetime | None) -> str | None:
    """SQLite returns naive values for UTC columns; keep the timezone explicit for browsers."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def analysis_out(a: Analysis, with_messages: bool = False, brief: bool = False) -> dict:
    summary = a.summary or {}
    if brief:  # lists of analyses do not need per-frame data
        summary = {k: v for k, v in summary.items() if k not in HEAVY}
    out = {
        "id": a.id,
        "mode": a.mode,
        "model": a.model,
        "shot": a.shot,
        "confidence": a.confidence,
        "uncertain": a.uncertain,
        "top3": a.top3,
        "angles": a.angles,
        "attention": a.attention,
        "summary": summary,
        "dtw": None if brief else a.dtw,
        "latency_ms": a.latency_ms,
        "created_at": timestamp(a.created_at),
        "original_name": a.media.original_name if a.media else None,
        "session_label": a.media.session_label if a.media else None,
        "files": {"original": f"/api/files/{a.id}/original", "output": f"/api/files/{a.id}/output"},
    }
    if with_messages:
        out["messages"] = [{"role": m.role, "text": m.text, "created_at": timestamp(m.created_at)}
                           for m in a.messages]
    return out
