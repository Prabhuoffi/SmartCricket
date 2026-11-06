"""Downloadable evidence for a player's own baseline and retest comparison."""
import io

from .pdf_report import DEEP, INK, M, MUTED, PAPER, W, ImageReader, Report, _fit
from .practice import PracticeError
from .practice_preview import capture_preview_bytes


def _safe_text(text):
    # Keep long user-entered words inside the printable area.
    return " ".join(word[i:i + 48] for word in str(text).split() for i in range(0, len(word), 48))


def comparison_pdf(data: dict, baseline, retest, goal: dict | None = None) -> bytes:
    report = Report("Comparison report", retest)
    report.heading("Baseline to retest")
    report.paragraph("Capture the same body side, shot, and stroke phase from a similar camera position. "
                     "These are measured changes in 2D angle estimates, not a score of batting skill or proof that practice caused a change.",
                     italic=False, color=INK, box=True)
    if goal:
        report.heading("Practice goal")
        report.paragraph(_safe_text(goal["title"]), size=11, italic=False, color=INK)
        focus = goal["focus_joint"].replace("_", " ").title()
        target = goal.get("target_deg")
        report.meta([("Focus joint", focus), ("Chosen target", f"{target:g} degrees" if target is not None else "Observe changes"),
                     ("Goal status", goal["status"])])
        if goal.get("notes"):
            report.paragraph(_safe_text(goal["notes"]), italic=False)
        if goal.get("due_date"):
            report.paragraph(f"Goal date: {goal['due_date']}. This is a player-selected practice milestone.")

    gap, height = 14, 180
    width = (W - 2 * M - gap) / 2
    report.need(height + 65)
    top = report.y
    for index, (label, analysis, capture) in enumerate((("BASELINE", baseline, data["baseline"]),
                                                      ("RETEST", retest, data["retest"]))):
        x = M + index * (width + gap)
        report.c.setFillColor(DEEP)
        report.c.roundRect(x, top - height, width, height, 7, stroke=0, fill=1)
        preview_available = False
        try:
            picture = ImageReader(io.BytesIO(capture_preview_bytes(analysis, capture["frame"])))
            iw, ih = picture.getSize()
            scale = min((width - 12) / iw, (height - 12) / ih)
            report.c.drawImage(picture, x + (width - iw * scale) / 2,
                               top - height + (height - ih * scale) / 2, iw * scale, ih * scale)
            preview_available = True
        except (OSError, ValueError, PracticeError):
            pass
        if not preview_available:
            report.c.setFillColor(PAPER)
            report.c.setFont("Helvetica", 9)
            report.c.drawCentredString(x + width / 2, top - height / 2, "Preview unavailable")
        report.c.setFillColor(INK)
        report.c.setFont("Helvetica-Bold", 9)
        frame = "" if capture["frame"] is None else f" - frame {capture['frame'] + 1} of {capture['frames']}"
        report.c.drawString(x, top - height - 16, label + frame)
        report.c.setFillColor(MUTED)
        report.c.setFont("Helvetica", 8)
        report.c.drawString(x, top - height - 29, _fit(capture["name"], "Helvetica", 8, width))
    report.y = top - height - 47
    report.paragraph(f"Baseline analysis saved: {data['baseline']['created_at']}. Retest analysis saved: {data['retest']['created_at']}.",
                     italic=False)
    report.heading("Comparison conditions")
    report.paragraph("Conditions checked; comparison still approximate." if data["comparable"]
                     else "Exploratory comparison: review the conditions below before interpreting angle changes.",
                     italic=False, color=INK, box=True)
    for check in data["checks"]:
        report.paragraph(_safe_text(f"{check['label']}: {check.get('detail', '')}"), italic=False)
    report.heading("Shared visible joints")
    report.table(["Joint", "Baseline", "Retest", "Retest - baseline"],
                 [[row["label"], f"{row['baseline_deg']:.1f} degrees", f"{row['retest_deg']:.1f} degrees",
                   f"{row['change_deg']:+.1f} degrees"] for row in data["rows"]], [.34, .21, .21, .24])
    if goal and goal.get("target_deg") is not None:
        row = next((row for row in data["rows"] if row["joint"] == goal["focus_joint"]), None)
        if row:
            before = abs(row["baseline_deg"] - goal["target_deg"])
            after = abs(row["retest_deg"] - goal["target_deg"])
            report.paragraph(f"Distance from your chosen target: baseline {before:.1f} degrees; retest {after:.1f} degrees. "
                             "Target distance is a numerical observation, not a judgement of correct technique.", italic=False)
        else:
            report.paragraph("The goal's focus joint was not visible in both captures, so target distance was not assessed.")
    if data.get("omitted"):
        report.paragraph("Excluded joints: " + "; ".join(f"{row['label']} ({row['reason']})" for row in data["omitted"]) + ".")
    report.paragraph(data["note"], box=True)
    return report.finish()
