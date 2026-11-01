"""CSV export and branded, print-ready HTML reports (FR-17)."""
import base64
import csv
import html
import io
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Analysis, Media, User
from ..video import overlay_kind
from ..pose import ANGLES
from .analyses import owned_analysis

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/history.csv")
def history_csv(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).join(Media).where(Media.user_id == user.id)
                      .order_by(Analysis.created_at)).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "date", "mode", "file", "session", "shot", "confidence", "uncertain", "visible_landmarks",
                *[f"{n}_deg" for n in ANGLES], "latency_ms"])
    for a in rows:
        ang = a.angles or {}
        w.writerow([a.id, a.created_at.isoformat(timespec="seconds"), a.mode, a.media.original_name,
                    a.media.session_label or "", a.shot or "", a.confidence if a.confidence is not None else "",
                    a.uncertain, (a.summary or {}).get("visible", ""),
                    *[(ang.get(n) or {}).get("deg") if (ang.get(n) or {}).get("deg") is not None else "" for n in ANGLES],
                    a.latency_ms])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=smartcricket_history.csv"})


@router.get("/{analysis_id}/pdf")
def report_pdf(analysis_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """One-click download: the branded report as a PDF file."""
    from .. import pdf_report
    a = owned_analysis(analysis_id, user, db)
    data = pdf_report.video_pdf(a) if a.mode == "video" else pdf_report.photo_pdf(a)
    kind = "Shot_analysis" if a.mode == "video" else "Posture_report"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="SmartCricket_{kind}_{a.id}.pdf"'})


@router.get("/{analysis_id}", response_class=HTMLResponse)
def report_html(analysis_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Branded, print-ready report. Images are embedded, so the page can be saved as PDF or HTML as it is."""
    a = owned_analysis(analysis_id, user, db)
    return _video_report(a) if a.mode == "video" else _photo_report(a)


# ---------------------------------------------------------------- shared page frame
BALL = ('<svg viewBox="0 0 64 64" width="44" height="44" aria-hidden="true"><defs><radialGradient id="rb" cx="38%" cy="32%" r="72%">'
        '<stop offset="0" stop-color="#f04a62"/><stop offset=".5" stop-color="#c8102e"/><stop offset="1" stop-color="#6a0614"/></radialGradient></defs>'
        '<circle cx="32" cy="32" r="30" fill="url(#rb)"/><g fill="none" stroke="#f3e9d2"><path d="M28.6 2.4Q22.6 32 28.6 61.6" stroke-width="1.7"/>'
        '<path d="M35.4 2.4Q29.4 32 35.4 61.6" stroke-width="1.7"/><path d="M24.9 6Q18.9 32 24.9 58" stroke-width="1.5" stroke-dasharray="1.4 2.8"/>'
        '<path d="M39.1 6Q33.1 32 39.1 58" stroke-width="1.5" stroke-dasharray="1.4 2.8"/></g>'
        '<ellipse cx="21" cy="17" rx="9" ry="5" fill="#fff" opacity=".28" transform="rotate(-35 21 17)"/></svg>')

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { margin: 0; background: #efe9da; font-family: 'Plus Jakarta Sans', Arial, sans-serif; color: #0b1a12;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.toolbar { position: sticky; top: 0; z-index: 5; display: flex; justify-content: center; gap: 10px; padding: 12px;
  background: rgba(239, 233, 218, .92); backdrop-filter: blur(8px); }
.toolbar button { font: 700 14px 'Plus Jakarta Sans', Arial, sans-serif; border: 0; border-radius: 99px; padding: 10px 18px; cursor: pointer; }
.toolbar .primary { background: #c8102e; color: #fff; box-shadow: 0 8px 18px -10px rgba(200, 16, 46, .9); }
.toolbar .ghost { background: #fff; color: #0a3d27; border: 1px solid rgba(11, 26, 18, .12); }
.sheet { width: 794px; max-width: 100%; margin: 8px auto 40px; background: #fffdf8; border-radius: 14px; overflow: hidden;
  box-shadow: 0 20px 50px -30px rgba(0, 0, 0, .45); }
.band { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 22px 30px; color: #fffdf8;
  background: radial-gradient(400px 160px at 85% 0, rgba(243, 233, 210, .14), transparent 70%), linear-gradient(135deg, #0a3d27, #062a1b); }
.brand { display: flex; align-items: center; gap: 12px; }
.brand b { display: block; font-family: Anton, Impact, sans-serif; font-weight: 400; font-size: 24px; letter-spacing: .05em; line-height: 1; }
.brand small { display: block; margin-top: 4px; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: rgba(243, 233, 210, .7); }
.doc { text-align: right; }
.doc b { display: block; font-family: Anton, Impact, sans-serif; font-weight: 400; font-size: 22px; letter-spacing: .04em; text-transform: uppercase; }
.doc span { font-size: 12px; color: rgba(243, 233, 210, .75); }
.redline { height: 4px; background: #c8102e; }
.content { padding: 24px 30px 10px; }
.meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
.meta div { background: #f6f0e2; border-radius: 10px; padding: 10px 12px; min-width: 0; }
.meta span { display: block; font-size: 10px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: #6b7a70; }
.meta b { display: block; margin-top: 3px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.main { display: grid; grid-template-columns: 1fr 220px; gap: 18px; align-items: stretch; margin-bottom: 22px; }
.photo { background: #04170e; border-radius: 12px; display: flex; justify-content: center; align-items: center; height: 380px; overflow: hidden; }
.photo img { max-width: 100%; max-height: 100%; display: block; }
.kpis { display: grid; grid-template-rows: repeat(4, 1fr); gap: 10px; }
.kpi { border: 1px solid rgba(11, 26, 18, .1); border-radius: 12px; padding: 10px 14px; display: flex; flex-direction: column; justify-content: center; }
.kpi span { display: block; font-size: 10px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: #6b7a70; }
.kpi b { display: block; font-family: Anton, Impact, sans-serif; font-weight: 400; font-size: 28px; line-height: 1.15; color: #0a3d27; }
.kpi b small { font-family: 'Plus Jakarta Sans', Arial, sans-serif; font-size: 13px; color: #6b7a70; }
.kpi.red b { color: #c8102e; }
.kpi > small { font-size: 11px; color: #6b7a70; }
h2 { font-family: Anton, Impact, sans-serif; font-weight: 400; font-size: 18px; letter-spacing: .05em; text-transform: uppercase; margin: 0 0 12px; }
h2::after { content: ""; display: block; width: 40px; height: 3px; margin-top: 5px; border-radius: 3px; background: #c8102e; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 20px; }
th { background: #0a3d27; color: #f3e9d2; text-align: left; font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase; padding: 9px 12px; }
th:first-child { border-radius: 8px 0 0 8px; } th:last-child { border-radius: 0 8px 8px 0; }
td { padding: 9px 12px; border-bottom: 1px solid rgba(11, 26, 18, .08); }
td.num { font-weight: 800; }
.pill { display: inline-block; padding: 3px 10px; border-radius: 99px; font-size: 11px; font-weight: 700; }
.ok { background: rgba(31, 157, 85, .14); color: #0f7a45; } .no { background: #efe9da; color: #6b7a70; }
.low { background: rgba(245, 158, 11, .16); color: #92400e; }
.bar { height: 6px; border-radius: 6px; background: #efe9da; overflow: hidden; width: 80px; display: inline-block; vertical-align: middle; margin-left: 8px; }
.bar i { display: block; height: 100%; background: #1f9d55; }
.notes { background: #f6f0e2; border-left: 4px solid #0f5c3a; border-radius: 0 10px 10px 0; padding: 12px 16px; font-size: 12.5px; margin-bottom: 14px; }
.notes ul { margin: 6px 0 0; padding-left: 18px; }
.disclaimer { font-size: 11.5px; color: #6b7a70; font-style: italic; margin: 0 0 18px; }
.strip { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 20px; }
.strip figure { margin: 0; position: relative; }
.strip img { width: 100%; border-radius: 6px; display: block; }
.strip figcaption { position: absolute; left: 4px; top: 4px; font-size: 10px; font-weight: 800; color: #fff; background: rgba(6, 42, 27, .8);
  padding: 1px 6px; border-radius: 99px; }
.strip .key img { outline: 3px solid #c8102e; outline-offset: -3px; }
.foot { display: flex; justify-content: space-between; gap: 10px; padding: 14px 30px; font-size: 11px; color: #6b7a70; border-top: 1px solid rgba(11, 26, 18, .08); }
@media print {
  body { background: #fff; } .toolbar { display: none; }
  .sheet { width: auto; margin: 0; border-radius: 0; box-shadow: none; }
  .main, table, .notes, .strip { break-inside: avoid; }
}
@media (max-width: 700px) { .meta { grid-template-columns: repeat(2, 1fr); } .main { grid-template-columns: 1fr; } .photo { height: 300px; } }
"""

TOOLBAR_JS = """
<script>
function downloadHtml() {
  const clone = document.documentElement.cloneNode(true);
  clone.querySelector('.toolbar')?.remove();
  clone.querySelectorAll('script').forEach(s => s.remove());
  const blob = new Blob(['<!doctype html>' + clone.outerHTML], { type: 'text/html' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = document.title.replace(/[^a-z0-9]+/gi, '_') + '.html';
  a.click();
}
</script>"""


def _page(title: str, a, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>SmartCricket AI {html.escape(title)}</title><style>{CSS}</style></head><body>'
            '<div class="toolbar"><button class="primary" onclick="print()">Download PDF</button>'
            '<button class="ghost" onclick="downloadHtml()">Download HTML</button>'
            '<button class="ghost" onclick="print()">Print</button></div>'
            '<div class="sheet">'
            f'<div class="band"><div class="brand">{BALL}<div><b>SMARTCRICKET AI</b><small>Batting analysis &amp; coaching</small></div></div>'
            f'<div class="doc"><b>{html.escape(title)}</b><span>{a.created_at:%d %b %Y, %H:%M}</span></div></div>'
            '<div class="redline"></div>'
            f'<div class="content">{body}</div>'
            f'<div class="foot"><span>Generated by SmartCricket AI on {datetime.now():%d %b %Y at %H:%M}</span>'
            '<span>M.E. CSE final-year project</span></div>'
            f'</div>{TOOLBAR_JS}</body></html>')


def _meta(a, last: tuple[str, str]) -> str:
    cells = [("Date", f"{a.created_at:%d %b %Y}"), ("Time", f"{a.created_at:%H:%M}"), last]
    return '<div class="meta">' + "".join(
        f"<div><span>{html.escape(k)}</span><b>{html.escape(str(v))}</b></div>" for k, v in cells) + "</div>"


def _img64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else ""


def _kpi(label: str, value: str, note: str = "", red: bool = False) -> str:
    return (f'<div class="kpi{" red" if red else ""}"><span>{label}</span><b>{value}</b>'
            + (f"<small>{note}</small>" if note else "") + "</div>")


# ---------------------------------------------------------------- photo report
def _photo_report(a) -> str:
    s = a.summary or {}
    img = ""
    if a.output_path and Path(a.output_path).exists():
        img = f'<img src="data:image/jpeg;base64,{_img64(Path(a.output_path))}" alt="Annotated photo">'
    order = sorted((a.angles or {}).items(), key=lambda kv: list(ANGLES).index(kv[0]) if kv[0] in ANGLES else 99)
    measured = sum(1 for _, v in order if v["deg"] is not None)
    rows = []
    for n, v in order:
        ok = v["deg"] is not None
        if ok and v["visibility"] >= .65:
            pill = '<span class="pill ok">&#10003; measured</span>'
        elif ok:
            pill = '<span class="pill low">less certain</span>'
        else:
            pill = '<span class="pill no">not visible</span>'
        angle = f"{v['deg']}&deg;" if ok else "&ndash;"
        rows.append(f"<tr><td>{html.escape(n.replace('_', ' ').title())}</td><td class='num'>{angle}</td>"
                    f"<td>{v['visibility']:.2f}<span class='bar'><i style='width:{v['visibility'] * 100:.0f}%'></i></span></td>"
                    f"<td>{pill}</td></tr>")
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in s.get("notes", []))
    tilt = s.get("shoulder_line_deg")
    visible, total = s.get("visible", 0), s.get("total", 33)
    kpis = (_kpi("Body points visible", f"{visible}<small> / {total}</small>")
            + _kpi("Angles measured", f"{measured}<small> / 8</small>", red=True)
            + _kpi("Shoulder tilt", "&ndash;" if tilt is None else f"{tilt}&deg;", "from horizontal")
            + _kpi("Analysis time", f"{a.latency_ms or 0}<small> ms</small>"))
    body = (_meta(a, ("Points visible", f"{visible} of {total}"))
            + f'<div class="main"><div class="photo">{img}</div><div class="kpis">{kpis}</div></div>'
            + '<h2>Joint angles</h2><table><tr><th>Joint</th><th>Angle</th><th>Visibility</th><th>Status</th></tr>'
            + "".join(rows) + "</table>"
            + (f'<div class="notes"><b>Notes</b><ul>{notes}</ul></div>' if notes else "")
            + '<p class="disclaimer">Angles are 2D estimates from one camera view. "Left" and "right" are the batter\'s own sides. '
              "They describe posture; they are not a judgement of correct or incorrect technique and not medical advice.</p>")
    return _page("Posture report", a, body)


# ---------------------------------------------------------------- video report
def _video_report(a) -> str:
    s = a.summary or {}
    d = Path(a.output_path)
    key = s.get("key_frame", 0)
    kind = overlay_kind(s) or "frame"
    frames = []
    for t in range(s.get("frames", 0)):
        cls = "key" if t == key else ""
        frames.append(f'<figure class="{cls}"><img src="data:image/jpeg;base64,{_img64(d / f"{kind}_{t:02d}.jpg")}" '
                      f'alt="frame {t + 1}"><figcaption>{t + 1}</figcaption></figure>')
    top3 = "".join(f"<tr><td>{i + 1}</td><td>{html.escape(r['shot'])}</td><td class='num'>{r['prob'] * 100:.1f}%"
                   f"<span class='bar'><i style='width:{r['prob'] * 100:.0f}%'></i></span></td></tr>"
                   for i, r in enumerate(a.top3 or []))
    att = s.get("attention") or []
    cmp = ""
    if a.dtw:
        rows = "".join(f"<tr><td>{html.escape(j.replace('_', ' ').title())}</td><td class='num'>{v['mean_abs_diff']}&deg;</td>"
                       f"<td>{v['mean_diff']:+}&deg;</td></tr>" for j, v in a.dtw["per_joint"].items() if v)
        cmp = ("<h2>Comparison with reference</h2>"
               f"<p style='font-size:13px;margin:0 0 10px'>Reference: <b>{html.escape(a.dtw['reference_label'])}</b> &middot; "
               f"DTW distance <b>{a.dtw['distance']}&deg;</b> per aligned frame (lower is closer).</p>"
               f"<table><tr><th>Joint</th><th>Mean difference</th><th>Player minus reference</th></tr>{rows}</table>")
    key_share = att[key] * 100 if att else 0
    if not a.shot:  # movement analysis: no shot label
        ranges = s.get("joint_ranges") or {}
        knees = [v["min"] for j, v in ranges.items() if j.endswith("knee")]
        kpis = (_kpi("Body tracked", f"{s.get('tracked_frames', 0)}<small> / {s.get('frames', 0)}</small>", "frames with 4+ angles")
                + _kpi("Most movement", f"Frame {key + 1}", f"{key_share:.1f}% of all movement", red=True)
                + _kpi("Deepest knee bend", f"{min(knees):.1f}<small>&deg;</small>" if knees else "-")
                + _kpi("Analysis time", f"{a.latency_ms or 0}<small> ms</small>"))
        rows = "".join(f"<tr><td>{html.escape(j.replace('_', ' ').title())}</td><td class='num'>{v['min']}&deg; (frame {v['min_frame'] + 1})</td>"
                       f"<td class='num'>{v['max']}&deg; (frame {v['max_frame'] + 1})</td><td class='num'>{v['range']}&deg;</td></tr>"
                       for j, v in ranges.items())
        body = (_meta(a, ("Model", s.get("model_label", a.model)))
                + f'<div class="main"><div class="photo"><img src="data:image/jpeg;base64,{_img64(d / f"{kind}_{key:02d}.jpg")}" alt="Key frame"></div>'
                + f'<div class="kpis">{kpis}</div></div>'
                + f"<h2>Joint ranges over the clip</h2><table><tr><th>Joint</th><th>Most bent</th><th>Most open</th><th>Range</th></tr>{rows}</table>"
                + f'<h2>All frames</h2><div class="strip">{"".join(frames)}</div>' + cmp
                + '<p class="disclaimer">Shot type was not identified: this clip was analysed for body movement only. '
                  "Joint angles are 2D estimates from one camera view and are not a judgement of technique or medical advice.</p>")
        return _page("Movement analysis report", a, body)
    kpis = (_kpi("Predicted shot", f'<span style="font-size:22px">{html.escape(a.shot or "-")}</span>', red=True)
            + _kpi("Calibrated confidence", f"{(a.confidence or 0) * 100:.1f}<small>%</small>",
                   "Uncertain" if a.uncertain else "Confident")
            + _kpi("Key frame", f"{key + 1}<small> / {s.get('frames', 0)}</small>", f"{key_share:.1f}% of attention")
            + _kpi("Analysis time", f"{a.latency_ms or 0}<small> ms</small>"))
    key_img = _img64(d / f"{kind}_{key:02d}.jpg")
    body = (_meta(a, ("Model", s.get("model_label", a.model)))
            + f'<div class="main"><div class="photo"><img src="data:image/jpeg;base64,{key_img}" alt="Key frame"></div>'
            + f'<div class="kpis">{kpis}</div></div>'
            + f"<h2>Top 3 shots</h2><table><tr><th>#</th><th>Shot</th><th>Probability</th></tr>{top3}</table>"
            + f'<h2>All frames</h2><div class="strip">{"".join(frames)}</div>'
            + cmp
            + '<p class="disclaimer">A heatmap shows where the model looked; it does not prove the model reasoned correctly. '
              "Joint angles are 2D estimates from one camera view and are not a judgement of technique or medical advice.</p>")
    return _page("Shot analysis report", a, body)
