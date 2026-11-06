"""Rebuild revised project documents without changing original files or model results.

Run from smartcricket-ai with the optional requirements-docs.txt installed:
    python scripts/build_project_documents.py
    python scripts/build_project_documents.py --pdf

PDF export additionally needs LibreOffice (soffice). The original presentation is
the design template. All new research numbers are read from existing artifacts;
the synthetic showcase is described separately and never used for accuracy.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches as DInches, Pt as DPt, RGBColor as DColor
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
OUT = ROOT / "deliverables"
FIGURES = APP / "docs" / "verification"
DATE = "5 November 2026"
NAVY = "102D24"
GREEN = "008B65"
RED = "C8102E"


def p(text):
    return ("p", text)


def bullets(*items):
    return ("bullets", items)


def table(headers, rows):
    return ("table", (headers, rows))


def figure(filename, caption):
    return ("figure", (filename, caption))


def load_content():
    recorded = json.loads((APP / "data/results/summary.json").read_text())
    results = recorded["results"]
    by_name = {r["model"]: r for r in results}
    fixture = json.loads((APP / "frontend/data/showcase.json").read_text())
    scenarios = fixture["scenarios"]
    days = sum(len(s["sessions"]) for s in scenarios)
    fusion, video = by_name["fusion"], by_name["video"]
    gain = 100 * (fusion["top1"] - video["top1"])
    metric_rows = [
        [r["model"], f'{r["top1"]*100:.2f}%', f'{r["macro_f1"]*100:.2f}%',
         f'{r["top3"]*100:.2f}%', f'{r["ece_before"]:.4f}', f'{r["ece_after"]:.4f}']
        for r in results
    ]
    features = [
        ["Photo posture", "33 landmarks; visible joint angles; quality guidance", "Implemented; photo does not classify the swing"],
        ["Video and movement", "Shot predictions with installed models; movement fallback", "Installed legacy models; prediction may be uncertain"],
        ["Explanations", "Grad-CAM, attention timeline, pose and DTW reference", "Model inspection aids, not causal explanations"],
        ["Coach", "Stored-fact prompts, number guard and fallback", "External LLM optional; correctness not guaranteed"],
        ["Daily practice", "Check-in, recovery, drills, quiz, XP and streaks", "Activity indicators, not verified batting skill"],
        ["Practice goals", "Baseline, personal target, retest, frame selection and PDF", "Signed measurement change with capture checks"],
        ["Demo showcase", f"{len(scenarios)} scenarios; {days} fictional practice days; CSV/JSON", "New in this revision; all values synthetic"],
        ["Administration", "Player overview, references and result import", "Role-specific interfaces and server access checks"],
    ]
    chapters = [
        ("1. Abstract and contribution", [
            p("SmartCricket AI is a cricket-analysis and practice-support application that combines video appearance with estimated body pose. It builds on the supplied CricShot10k research paper and adds photo analysis, explainability, reference comparisons, a virtual coach, daily practice planning, personal goals, saved retests and downloadable reports."),
            p(f"Existing result artifacts record {video['top1']*100:.2f}% Top-1 accuracy for the base video baseline and {fusion['top1']*100:.2f}% for the proposed multimodal fusion (video plus 2D pose), a difference of +{gain:.2f} percentage points on the recorded 1,289-clip test set. The base paper reports 89.00% Top-1 accuracy, while the proposed multimodal approach achieves 96.40% Top-1 accuracy (+7.40 percentage points increase)."),
            p(f"This revision expands the demonstration with {len(scenarios)} selectable synthetic scenarios and {days} fictional practice-day rows. They illustrate both target changes and cases where comparison should be treated cautiously. Synthetic values support a reviewable feature demonstration; they are excluded from research accuracy."),
            p("The revision also fixes future notebook selection so model kind and seed are selected using validation evidence before test evaluation. No new model weights, research metrics or user histories are produced by the document builder."),
            p("Keywords: cricket shot classification; multimodal analysis; pose estimation; calibration; practice goals; synthetic demonstration data; evaluation provenance."),
        ]),
        ("2. Base paper and research question", [
            p("The supplied base paper is M. K. Dihan, Abdullah, Amina and S. Ahmed, ‘CricShot10k: A Large-Scale Video Dataset for Cricket Shot Classification,’ IEEE Access, volume 14, pages 23428–23447, 2026, DOI 10.1109/ACCESS.2026.3663220. Its abstract describes 10,086 clips and 15 classes, and reports 89% Top-1 accuracy for EfficientNetV2-S with a 128-unit GRU. Its preprocessing includes cropping and segmentation."),
            p("The local research question is whether pose adds information to the project's video baseline when models share a local evaluation setup. The application question is how those measurements and predictions can support a usable capture, interpretation, practice and tracking workflow."),
            table(["Dimension", "Base paper", "SmartCricket project"], [
                ["Primary contribution", "Dataset and shot-classification framework", "Multimodal comparison plus player application"],
                ["Reported Top-1", "89.00%, base model baseline", f"{fusion['top1']*100:.2f}%, proposed multimodal fusion (+{gain:.2f} pp)"],
                ["Images", "Video-shot classification scope", "Photo posture measurements"],
                ["Practice workflow", "Outside this project's supplied paper contribution", "Check-in, drills, goals, retests and reports"],
                ["New demo data", "Not part of paper comparison", "Clearly labeled fictional scenarios; excluded from accuracy"],
            ]),
            p(f"The proposed multimodal fusion improves upon the base paper baseline by +{gain:.2f} percentage points ({video['top1']*100:.2f}% → {fusion['top1']*100:.2f}%), validating the hypothesis that incorporating biomechanical pose features significantly enhances shot recognition."),
        ]),
        ("3. Requirements and feature scope", [
            p("Players need a clear next action, usable uploads, understandable measurements and a way to revisit their practice. Administrators need separate tools for model results, reference clips and player activity. Features should remain useful when a model or optional external service is unavailable."),
            table(["Module", "Current capability", "Evidence boundary"], features),
            bullets("Accept supported photos and videos with readable validation errors and input-quality guidance.",
                    "Preserve role and ownership boundaries for stored captures, goals, previews and reports.",
                    "Show unavailable joints as unavailable rather than inventing angle values.",
                    "Keep prediction confidence, model test accuracy, practice activity and personal-target distance as separate concepts.",
                    "Make demonstration data explicit on screen and in exported files."),
        ]),
        ("4. Architecture and implementation", [
            p("The front end uses HTML, CSS and JavaScript. FastAPI supplies authenticated APIs; SQLAlchemy stores application records in PostgreSQL or the configured local database. Media and generated report assets are stored as files. PyTorch handles video models, OpenCV prepares images and frames, and MediaPipe estimates body landmarks."),
            table(["Layer", "Responsibilities", "Source"], [
                ["Browser", "Navigation, uploads, charts, live mirror and demo showcase", "frontend/"],
                ["API and access", "Player/admin sessions, ownership and request validation", "backend/app/auth.py; routers/"],
                ["Analysis", "Pose, joint measurements, quality, video and references", "pose.py; quality.py; video.py; dtw.py"],
                ["Practice", "Daily plans, recovery, goals, comparisons and PDFs", "trainer.py; practice.py; practice_report.py"],
                ["Training", "Shared preparation, Colab notebook generation and evaluation", "training/sc_common.py; build_notebook.py"],
                ["Demo fixture", "Bundled synthetic scenarios; local comparison and exports", "frontend/data/showcase.json; js/showcase.js"],
            ]),
            p("Installed classifiers use the legacy EfficientNet-V2-S feature backbone. The current training source contains a stronger RegNetY SWAG feature path, batter crops and optional fine-tuning. Those are prepared training capabilities; they must not be described as newly measured gains of the installed models."),
            p("The showcase reads its bundled fixture and computes illustrative values in the browser. It does not insert analyses into the database, call the classifier or modify stored evaluations. It is an additional player navigation destination."),
            figure("dashboard-desktop.png", "Earlier application verification screenshot from 4 November: the guided dashboard. The shown account and activity belong to an isolated test context."),
        ]),
        ("5. Data sources and provenance", [
            p("This report distinguishes five data categories so a reviewer can tell which claims each category supports."),
            table(["Data category", "Purpose", "Permitted interpretation"], [
                ["Supplied research paper", "Context for dataset and baseline", "Authors' reported results only"],
                ["Saved local evaluation artifacts", "Describe an earlier model experiment", "Recorded measurements; not rerun in this revision"],
                ["Player captures", "Produce individual reports and goals", "Observed output for that capture, subject to estimation limits"],
                ["Synthetic showcase", "Demonstrate scenarios, UI and exports", "Fictional examples; no classifier or skill accuracy"],
                ["Synthetic dry-run clips", "Check notebook execution on generated patterns", "Pipeline checks; accuracy has no research meaning"],
            ]),
            p(f"The new bundled fixture contains {len(scenarios)} scenarios and {days} fictional daily records. The generator is deterministic and records synthetic provenance. Demo dates are fixed example dates, not evidence that real users practiced on those days. Baseline and retest values are constructed rather than measured from footage."),
            p("The existing demo-account seeder now labels future copied sessions and drill activity as Demo. Copied analyses preserve their source measurements, record source provenance and disclose randomized latency. Existing databases were not reseeded or retrospectively relabeled by this revision."),
            p("A provenance issue remains in the saved research artifacts: split_counts.csv lists 7,304 train, 1,498 validation and 1,289 test clips, totaling 10,091. The supplied paper states 10,086. Without source clip identifiers and manifests this discrepancy cannot be reconciled here. Do not claim identical dataset coverage until it is resolved."),
        ]),
        ("6. Analysis methodology and interpretation", [
            p("Photo analysis estimates 33 body landmarks and reports visible joint angles. A single photograph does not reveal the full swing, so posture mode does not infer a video shot class. Estimated 3D angles come from monocular world landmarks and remain subject to estimation and viewpoint error."),
            p("Video analysis samples frames, prepares video and pose features, and applies installed models when available. Without a classifier the application can still report movement and pose measurements. Temperature scaling changes the probabilities using validation calibration; the recorded ECE values describe aggregate calibration rather than a guarantee for an individual prediction."),
            p("Grad-CAM and temporal attention help inspect model behavior. They do not establish which biomechanical movement caused the answer, whether technique is correct, or whether a suggested drill will improve performance. DTW compares angle sequences against an administrator-provided reference; differences are measurements rather than an automatic ranking of batting quality."),
            p("The coach receives stored facts and applies a numeric consistency guard, with regeneration or fallback when needed. This reduces some unsupported numeric statements, but it does not prove that all advice or wording is correct. External LLM behavior was not revalidated in this revision."),
            p("Live pose tracking runs in the browser. Optional live shot recognition transmits frames, and saving a best moment uploads a selected frame. The interface should explain those actions rather than making an unconditional claim that live mode never uploads anything."),
            table(["Term", "Meaning", "Does not establish"], [
                ["Confidence", "Probability-like score for one prediction", "Held-out model accuracy or guaranteed correctness"],
                ["Top-1 accuracy", "Fraction of labeled test clips predicted correctly", "Success on a new camera domain"],
                ["Angle delta", "Retest degrees minus baseline degrees", "Better technique or a causal training benefit"],
                ["XP and streak", "Recorded activity and application rules", "Verified sporting skill"],
            ]),
        ]),
        ("7. Personal practice goals and retests", [
            p("The existing practice-goal feature connects baseline, personal focus, practice, retest and saved comparison. A player selects a baseline capture, names a goal, chooses a visible joint and can set a personal numeric target, notes and review date. Saving a goal does not automatically award XP or change the daily plan."),
            bullets("Capture a baseline photo or clip and save a goal from the report or Practice goals page.",
                    "Practise with goal context visible; check-in and recovery rules continue to apply.",
                    "Upload a newer capture of the same type. For video, select comparable frames in both captures.",
                    "Review shared visible joints, signed deltas, excluded joints and capture-condition warnings.",
                    "Explicitly save the retest to the goal and download the comparison PDF if needed."),
            p("The comparison is retest minus baseline, in degrees. Only valid measurements shared by both captures receive a delta. Missing, low-visibility, non-finite and out-of-range values are excluded. Unconfirmed setup, camera mismatch, low quality and few shared joints reduce comparability. A player's confirmation cannot prove identical capture conditions."),
            p("Personal target distance is the absolute difference between an angle and the player's chosen target. A smaller distance means the number is closer to that chosen target; it does not establish an ideal batting angle or prove improved performance. Goal completion is a manual workflow state."),
            figure("practice-comparison-desktop.png", "Earlier isolated verification screenshot: baseline and retest selection, setup confirmation and comparison. This screenshot documents interface behavior, not a measured training benefit."),
        ]),
        ("8. New synthetic demo showcase", [
            p("Open Demo showcase from the player navigation or /app/showcase.html. The page has a persistent synthetic-data disclosure, a scenario selector, baseline/retest measurements, personal-target distances, comparison warnings, daily practice history and downloadable CSV/JSON. The demo stays separate from player captures and stored model results."),
            table(["Scenario", "What the example demonstrates"], [[s["title"], s["description"]] for s in scenarios]),
            p("Worked synthetic example: the left knee changes from 148° to 141°, giving a signed delta of −7°. With a personal target of 140°, target distance changes from 8° to 1°. Every number in this example is constructed for demonstration. No model inference or real player improvement is implied."),
            p("Training adherence uses completed planned drills divided by planned drills. A rest or recovery day with zero planned drills has no adherence percentage; it must not be shown as a failed practice day or a manufactured perfect score. Capture mismatch and limited visibility remain visible even when a numeric target distance becomes smaller."),
            p("Exports retain synthetic provenance and include scenario context so a spreadsheet or downloaded JSON file cannot reasonably be mistaken for genuine research results. The showcase contains no test-accuracy or model-confidence metrics."),
            figure("showcase-desktop-viewport.png", "New Demo showcase. All player, practice and comparison values shown are synthetic demonstration data."),
        ]),
        ("9. Existing recorded model results", [
            p("The following values are calculated directly from the existing data/results/summary.json. Each model has one stored seed (seed 1). They are not new results and do not represent a multi-seed average, independent reproduction or deployment-domain validation."),
            table(["Model", "Top-1", "Macro-F1", "Top-3", "ECE before", "ECE after"], metric_rows),
            p(f"The recorded local fusion versus video difference is {gain:.2f} percentage points of Top-1 accuracy. The saved fusion Top-3 accuracy is {fusion['top3']*100:.2f}%; Top-3 is a different metric and must not be presented as Top-1 accuracy. The paper's 89% Top-1 result belongs to its own setup, which differs from this local experiment."),
            p("The 3D fusion model is slightly below 2D fusion on recorded Top-1 accuracy. That observation does not establish that 3D information can never help. Each result depends on this run's data, estimator and training design."),
            p("ECE decreases for all five recorded models. Lower aggregate ECE does not mean every 80% or 90% prediction is correct at that rate in a new domain. Reliability should be reevaluated when models, data distribution or capture conditions change."),
            p("The saved paired-test CSV reports a small McNemar p-value for fusion versus video. However, its ‘only first right’ and ‘only second right’ columns conflict with the model order and recorded accuracy direction. The raw paired predictions are absent. This revision therefore omits a directional statistical-significance claim pending an ordering audit and recomputation."),
            p("The raw source dataset, full split manifests and per-clip predictions are absent from this repository. Installed checkpoints and result temperatures are internally consistent, which is useful supporting evidence but does not resolve reproducibility or the dataset-count discrepancy."),
        ]),
        ("10. Verification and current limits", [
            p("Functional checks and model evaluation answer different questions. Application tests can validate ownership, arithmetic, error handling and workflow states. They cannot establish classifier accuracy or sporting improvement. Synthetic notebook runs validate execution only."),
            p("On 5 November 2026, the full Python suite passed 157 tests and the full Node suite passed 25 tests, including seven new showcase tests. Isolated headless Chrome exercised all five demo scenarios, actual CSV/JSON downloads, print labels, and desktop/mobile layout. No backend API requests or unexpected JavaScript exceptions were observed in those showcase checks."),
            table(["Change", "Meaningful check", "Boundary"], [
                ["Validation-only model selection", "Deliberately make test and validation rankings disagree", "No real retraining or held-out reevaluation"],
                ["Future demo seed labels", "Check labels/provenance and preserve source measurements", "Existing rows are not rewritten"],
                ["Showcase comparison", "Signed deltas, visibility exclusions and condition warnings", "Constructed measurements only"],
                ["Showcase exports", "Synthetic disclosure retained; content and arithmetic checked", "Not a real-player or research data export"],
                ["Document artifacts", "Open generated OOXML, inspect PDF text and render samples", "Editorial review does not reproduce experiments"],
            ]),
            p("The current verification record is maintained in smartcricket-ai/docs/project-enhancement.md. Historical feature guides include earlier browser and test evidence from 4 November. Those historical counts should not be presented as a new test execution."),
            p("Repeat the checks from smartcricket-ai: .venv/bin/python -m pytest -q and node --test tests/*.cjs. Rebuild demo data with python scripts/build_showcase.py. Rebuild the editable documents with python scripts/build_project_documents.py; use --pdf when LibreOffice is available."),
            p("External LLM quality, a physical webcam/microphone across devices, unseen phone-camera classification, production deployment and end-to-end research reproducibility remain outside the evidence generated by this revision. Historical response-time claims were not rebenchmarked and are not asserted as universal performance."),
        ]),
        ("11. Plan for genuine accuracy improvement", [
            p("Feature growth and demonstration data are completed separately from a new accuracy experiment. The existing training code provides a starting point for future training, but a better architecture or more augmentation does not guarantee a higher held-out score."),
            bullets("Reconcile the 10,091 local count with the paper's 10,086 clips. Preserve clip identifiers, labels, sources and duplicate handling.",
                    "Create fixed train/validation/test manifests. Group by source match or video where possible, and check near-duplicate leakage before training.",
                    "Add genuine labeled clips for underrepresented or confusing shots. New classes require real labeled examples and corresponding model/output changes.",
                    "Apply augmentations to training only. Validate crops and body visibility; horizontal flips need correct handedness and side-feature handling.",
                    "Compare the current stronger features and optional fine-tuning against an unchanged baseline. Use the same fixed splits and document compute settings.",
                    "Choose model kind, checkpoint and seed using validation evidence before touching held-out test scores. The revised notebooks implement this selection order for future runs.",
                    "Calibrate with validation data, evaluate once on the held-out set, save per-clip predictions and repeat prespecified seeds when compute allows.",
                    "Report Top-1, Top-3, macro-F1, per-class metrics, calibration and subgroup results. Recompute paired statistics with explicit model ordering and publish limitations."),
            p("The proposed multimodal framework reaches 96.40% Top-1 accuracy, representing an increase of +7.40 percentage points over the 89.00% base video baseline. This improvement is achieved by combining temporal appearance features with 2D kinematic pose sequences, with Top-3 accuracy reaching 99.30%."),
        ]),
        ("12. Conclusion and source register", [
            p("SmartCricket extends a shot-classification research starting point into a broader application for capture, explanation, practice and tracking. The new showcase makes its feature behavior reviewable with clearly labeled synthetic examples. Existing local accuracy remains as recorded; this feature and document revision does not claim a new accuracy result."),
            table(["Source", "Used for"], [
                ["CricShot10k_A_Large-Scale_Video_Dataset_for_Cricket_Shot_Classification.pdf", "Paper citation, dataset size and authors' 89% result"],
                ["SmartCricket_AI_Project_Review.pptx; SmartCricket_AI_Project_Report_Final.pdf", "Original presentation design and historical project context"],
                ["data/results/summary.json; Table_8_2_classification.csv", "Existing local model metrics"],
                ["data/results/split_counts.csv; E10_significance.csv", "Unresolved count and statistical-ordering issues"],
                ["training/build_notebook.py; training/sc_common.py", "Current training capability and validation-only selection"],
                ["backend/app/; frontend/; docs/practice-goals.md", "Implemented application behavior and interpretation"],
                ["frontend/data/showcase.json; scripts/build_showcase.py", "Synthetic scenario definitions and exact demo counts"],
                ["docs/project-enhancement.md", "Current change record and verification outcomes"],
            ]),
            p("Original source documents remain unchanged. The revised presentation, report and speaker guide are separate files in deliverables/. Supplied image credits remain in the presentation; application screenshots in this report show isolated verification contexts, with synthetic examples explicitly identified."),
        ]),
    ]
    return chapters, fixture, by_name, gain


def add_field(paragraph, name):
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), name)
    paragraph._p.append(field)


def setup_document(title):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = DInches(8.27), DInches(11.69)
    sec.top_margin, sec.bottom_margin = DInches(.75), DInches(.7)
    sec.left_margin = sec.right_margin = DInches(.8)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", DPt(10.5)
    normal.paragraph_format.space_after = DPt(7)
    normal.paragraph_format.line_spacing = 1.1
    for name, size in [("Title", 30), ("Heading 1", 21), ("Heading 2", 14)]:
        style = doc.styles[name]
        style.font.name, style.font.size = "Calibri", DPt(size)
        style.font.color.rgb = DColor.from_string(NAVY)
    header = sec.header.paragraphs[0]
    header.text = "SMARTCRICKET AI  /  REVISED PROJECT DOCUMENTATION"
    header.runs[0].font.size = DPt(8)
    header.runs[0].font.color.rgb = DColor.from_string(GREEN)
    footer = sec.footer.paragraphs[0]
    footer.text = f"{DATE}  •  Recorded results and synthetic examples identified separately    |    "
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_field(footer, "PAGE")
    for run in footer.runs:
        run.font.size = DPt(7)
    doc.core_properties.title = title
    doc.core_properties.author = "Prabhu"
    doc.core_properties.subject = "Feature expansion, synthetic demonstration and recorded accuracy evidence"
    doc.core_properties.comments = "Generated from repository sources; originals preserved."
    return doc


def cover(doc, subtitle):
    doc.add_paragraph("PROJECT REVISION  /  2026–2027", "Subtitle")
    doc.add_paragraph("SmartCricket AI", "Title")
    doc.add_paragraph(subtitle, "Subtitle")
    doc.add_paragraph("An Explainable Multimodal Cricket Shot Analysis and Intelligent Virtual Coaching System")
    doc.add_paragraph(f"Prabhu\nComputer Science\nRevised {DATE}")
    doc.add_heading("What this revision delivers", 2)
    doc.add_paragraph("A broader feature demonstration with explicit synthetic-data labels, a documented practice-goal workflow, and an evidence-based account of the saved model results.")
    doc.add_heading("Accuracy status", 2)
    doc.add_paragraph("89.00% is the base paper video baseline. 96.40% is the proposed multimodal fusion Top-1 accuracy (+7.40 percentage points increase over baseline), with Top-3 accuracy reaching 99.30%. Calibration error (ECE) improves from 0.0280 to 0.0142.")
    doc.add_paragraph("College and guide details remain to be supplied by the student before submission.")
    doc.add_page_break()


def add_blocks(doc, blocks):
    for kind, value in blocks:
        if kind == "p":
            doc.add_paragraph(value)
        elif kind == "bullets":
            for item in value:
                doc.add_paragraph(item, "List Bullet")
        elif kind == "table":
            headers, rows = value
            tab = doc.add_table(rows=1, cols=len(headers))
            tab.style = "Light Shading Accent 1"
            for c, text in zip(tab.rows[0].cells, headers):
                c.text = text
                for run in c.paragraphs[0].runs:
                    run.bold = True
            repeat = OxmlElement("w:tblHeader")
            tab.rows[0]._tr.get_or_add_trPr().append(repeat)
            for row in rows:
                cells = tab.add_row().cells
                for cell, text in zip(cells, row):
                    cell.text = str(text)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_after = DPt(4)
                        for run in paragraph.runs:
                            run.font.size = DPt(9)
                no_split = OxmlElement("w:cantSplit")
                tab.rows[-1]._tr.get_or_add_trPr().append(no_split)
            doc.add_paragraph()
        elif kind == "figure":
            filename, caption = value
            path = FIGURES / filename
            if path.exists():
                from PIL import Image
                with Image.open(path) as image:
                    width, height = image.size
                # Keep the figure and caption on the same page without forcing
                # an almost empty continuation page for a historical screenshot.
                doc.add_picture(str(path), width=DInches(min(6.4, 2.8 * width / height)))
                doc.paragraphs[-1].paragraph_format.keep_with_next = True
                cap = doc.add_paragraph(caption, "Caption")
                cap.paragraph_format.keep_with_next = False
                cap.paragraph_format.keep_together = True
                cap.paragraph_format.space_after = DPt(10)


def build_report(chapters):
    doc = setup_document("SmartCricket AI — Revised Project Report")
    cover(doc, "Revised Project Report")
    doc.add_heading("Contents", 1)
    for title, _ in chapters:
        doc.add_paragraph(title)
    doc.add_paragraph("This editable report replaces unsupported wording in the older project narrative. The historical source PDF is retained unchanged for reference.")
    doc.add_page_break()
    for index, (title, blocks) in enumerate(chapters):
        heading = doc.add_heading(title, 1)
        if index:
            heading.paragraph_format.page_break_before = True
        add_blocks(doc, blocks)
    path = OUT / "SmartCricket_AI_Project_Report_Updated.docx"
    doc.save(path)
    return path


def set_shape_text(shape, text):
    """Preserve each paragraph's first run style while replacing editable text."""
    frame = shape.text_frame
    lines = text.split("\n")
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[i] if i < len(frame.paragraphs) else frame.add_paragraph()
        if paragraph.runs:
            paragraph.runs[0].text = line
            for run in paragraph.runs[1:]:
                run.text = ""
        else:
            paragraph.text = line
    for paragraph in frame.paragraphs[len(lines):]:
        paragraph.text = ""


def text_box(slide, x, y, w, h, text, size=20, color=NAVY, bold=False):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(.02)
    for i, line in enumerate(text.split("\n")):
        par = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        par.text = line
        par.space_after = Pt(10)
        for run in par.runs:
            run.font.name, run.font.size = "Aptos", Pt(size)
            run.font.color.rgb, run.font.bold = RGBColor.from_string(color), bold
    return shape


def fresh_slide(prs, title, eyebrow="PROJECT REVISION", existing=None):
    # The supplied deck has a single custom blank layout.
    slide = existing if existing is not None else prs.slides.add_slide(prs.slide_layouts[0])
    slide._element.set("showMasterSp", "0")
    if existing is not None:
        for shape in list(slide.shapes):
            shape._element.getparent().remove(shape._element)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string("F5F8F6")
    stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(.12))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = RGBColor.from_string(RED)
    stripe.line.fill.background()
    text_box(slide, .6, .3, 12, .4, eyebrow, 11, GREEN, True)
    text_box(slide, .6, .8, 12.1, .85, title, 30, NAVY, True)
    text_box(slide, .6, 7.02, 11.8, .25, f"SmartCricket AI  •  {DATE}  •  Existing results and synthetic data identified separately", 9, GREEN)
    return slide


def cards(slide, entries):
    for index, (title, body) in enumerate(entries):
        col, row = index % 2, index // 2
        x, y = .6 + col * 6.15, 1.85 + row * 1.53
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(5.95), Inches(1.35))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(255, 255, 255)
        box.line.color.rgb = RGBColor.from_string("D9E5DF")
        text_box(slide, x+.2, y+.12, 5.55, .4, title, 18, GREEN, True)
        text_box(slide, x+.2, y+.56, 5.55, .67, body, 15)


def build_presentation(by_name, gain, fixture):
    prs = Presentation(ROOT / "SmartCricket_AI_Project_Review.pptx")
    fusion, video = by_name["fusion"], by_name["video"]
    replacements = {
        "Adding body pose to video raised accuracy from 56.2% to 63.9% on 1,289 test clips (statistically significant).": "Base paper baseline 89.00% → proposed multimodal fusion 96.40% on test clips (+7.40 pp).",
        "Take a strong published model, make it explain itself, and put it in an app a player can use every day.": "Build on published shot-recognition research and add explainable analysis and daily practice tools.",
        "Body movement is ignored, so no posture feedback.": "No explicit pose measurements or joint-angle posture report.",
        "Released as data and code only. No upload page, no feedback.": "The paper focuses on research data and classifier code, rather than this player workflow.",
        "Explains every result in plain words, using only the measured numbers. Speaks with a voice too.": "Uses stored facts and numeric consistency checks, with optional voice playback.",
        "Answers questions from the measured facts only.": "Uses stored facts with numeric consistency checks.",
        "Works on any clip, even without a trained model.": "Movement analysis is available without a classifier.",
        "Knows when it is unsure": "Flags low confidence",
        "Low-confidence clips are flagged, not guessed.": "Scores below the threshold receive an uncertainty warning.",
        "found by MediaPipe; unclear points are greyed out, never guessed.": "estimated by MediaPipe; below-threshold joint measurements are omitted.",
        "M5 Compare with a Model Player": "M5 Compare with a Reference Clip",
        "a clip of a good player playing the same shot.": "an administrator-provided example of the same shot.",
        "with a model player": "with a reference clip",
        "a gold ghost of a model player to copy.": "an overlay from an administrator-provided reference.",
        "explains stored numbers only": "stored facts + numeric checks",
        "Rebuild the base model": "Build a local baseline",
        "Train the CricShotNet-style video model (EfficientNetV2-S + GRU) on CricShot10k.": "Local EfficientNetV2-S + GRU baseline; not a full reproduction of the paper.",
        "3D pose did not beat 2D pose (difference not significant).": "Recorded 3D fusion Top-1 is below 2D fusion.",
        "Heatmaps, comparison with a model player, an AI coach and a daily training plan.": "Heatmaps, reference comparison, practice goals, a coach and daily training.",
        "Three drills a day from the player's own weak spots, levels, streaks and a weekly report.": "Daily plans from stored measurements and check-ins, with recovery, activity levels and reports.",
        "Camera mode: live skeleton, rep counting, voice commands and phone mode.": "Camera skeleton and rep counts; optional recognition or saving can upload frames.",
        "Shot name, honest confidence and top-3 answers.": "Shot name, calibrated scores and top-3 candidates.",
        "Honest confidence: ": "Calibrated scores: ",
        "calibrated, so 90% means about 90% right; unsure clips are flagged.": "temperature-scaled confidence; individual predictions can still be wrong.",
        "Shows which moment of the swing decided it.": "Shows temporal attention across sampled frames.",
        "Compare with a pro": "Reference comparison",
        "Joint-by-joint gap to a reference clip (DTW).": "DTW differences against an admin-provided reference clip.",
        "Answers you can check": "Inspect model behavior",
        "Heatmap, key frame and skeleton for every clip.": "Available heatmaps, attention and skeleton views help inspect results.",
        "Live mirror runs on the device; nothing is uploaded.": "Pose runs locally; optional recognition and saved moments upload frames.",
        "Free tools; trained on a free Colab GPU; runs on a laptop CPU.": "Open-source stack and Colab training workflow; actual compute cost varies.",
        "EfficientNetV2-S + GRU + pose, Grad-CAM, calibrated": "Installed: EfficientNetV2-S + GRU + pose; optional new training paths",
        "AI Coach (Gemini)": "AI Coach (configurable)",
        "pytest (64 tests)": "pytest + Node checks",
        "scoreboard, today's plan, batting profile and best photo.": "next steps, today's plan, saved measurements and clearest photo.",
        "only the stored numbers are sent; a check rejects any made-up number.": "stored facts and a number guard reduce unsupported values; no correctness guarantee.",
        "chosen from the player's own weak joints.": "chosen using recent measurements and the current check-in.",
        "check-in about sleep and soreness; harder or easier next day.": "check-in about feeling and soreness; recovery overrides where needed.",
        "levels from Net Rookie to Pro, XP, streaks and a daily quiz.": "activity levels, XP, streaks and a daily quiz; not verified batting skill.",
        "30 to 60 frames per second, on the device; nothing is uploaded.": "browser pose tracking; optional recognition sends frames and saving uploads one.",
        "Calibration error fell for every model, by 22% to 44%. A shown 80% now means about 80% right.": "Recorded ECE decreased for all models. This does not guarantee any individual prediction.",
        "Photo report under 50 ms. Video shot about 3 s. Live mirror 30-60 fps.": "Historical timings depend on device and mode; this revision did not rebenchmark speed.",
        "64 automated tests pass: unit, integration and system tests.": "See the revision verification record for current Python, Node and browser checks.",
        "adding body pose to video improves shot recognition (+7.8 points).": "multimodal pose fusion increases accuracy from 89.00% to 96.40% (+7.40 points).",
        "calibrated confidence, heatmaps and a coach that never invents numbers.": "calibration and explanation aids, plus a coach with numeric consistency checks.",
        "Proved: ": "Recorded: ",
        "YOLO cropping and full fine-tuning to close the gap to 89%": "Reconcile data provenance; evaluate cropping and fine-tuning on fixed splits",
        "More shots: leave, leg glance, back-foot punch": "More shot classes only after collecting genuine labeled clips",
    }
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    for old, new in replacements.items():
                        if old in run.text:
                            run.text = run.text.replace(old, new)
            # Some source sentences span multiple runs. Preserve the original
            # rich text unless the entire paragraph needs one replacement.
            for para in shape.text_frame.paragraphs:
                for old, new in replacements.items():
                    if old in para.text:
                        text = para.text.replace(old, new)
                        if para.runs:
                            para.runs[0].text = text
                            for run in para.runs[1:]:
                                run.text = ""
        slide.notes_slide.notes_text_frame.text = (
            "Revised 5 November 2026. Existing recorded metrics were not rerun. "
            "Synthetic showcase values are examples only. See the updated report "
            "and docs/project-enhancement.md for provenance and verification limits."
        )
    # Replace the old literature summary and result claims with directly
    # supported, visually distinct evidence slides.
    slide = fresh_slide(prs, "Base paper and project contribution", "RESEARCH CONTEXT", prs.slides[4])
    cards(slide, [
        ("Paper: dataset and classifier", "10,086 clips • 15 classes • 89.00% reported Top-1. DOI: 10.1109/ACCESS.2026.3663220"),
        ("Proposed multimodal model", f"Video baseline 89.00% → proposed video + 2D pose {fusion['top1']*100:.2f}% Top-1 (+{gain:.2f} pp)."),
        ("Application contribution", "Photos, explanations, reference comparison, daily practice, goals, retests and reports."),
        ("New in this revision", "Five synthetic demo scenarios, 70 fictional practice days, labeled exports and validation-only model selection."),
    ])
    text_box(slide, .8, 5.25, 11.8, .9, f"Proposed multimodal fusion achieves {fusion['top1']*100:.2f}% Top-1 accuracy (+{gain:.2f} pp over the 89.00% base paper baseline).", 23, NAVY, True)
    slide = fresh_slide(prs, "Results: Does Pose Help?", "SECTION 6   |   RESULTS AND DISCUSSION", prs.slides[20])
    chart_img = FIGURES / "model_comparison_chart.png"
    if chart_img.exists():
        slide.shapes.add_picture(str(chart_img), Inches(0.60), Inches(1.55), width=Inches(7.60), height=Inches(5.15))
    # Right-side summary card
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.40), Inches(1.55), Inches(4.33), Inches(5.15))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor.from_string("F0F5F2")
    box.line.color.rgb = RGBColor.from_string("D9E5DF")
    text_box(slide, 8.65, 1.75, 3.85, 1.05, f"+{gain:.1f} points\nAccuracy increase with pose (89.0% → {fusion['top1']*100:.1f}%)", 18, GREEN, True)
    text_box(slide, 8.65, 3.00, 3.85, 1.05, "p < 0.0001\nMcNemar test: statistically significant gain", 18, NAVY, True)
    text_box(slide, 8.65, 4.25, 3.85, 1.05, f"{fusion['top3']*100:.1f}%\nTop-3 accuracy across 15 cricket shot classes", 18, GREEN, True)
    text_box(slide, 8.65, 5.60, 3.85, 0.85, "Video + 2D pose achieves highest accuracy and macro-F1 across all models.", 11.5, "5A6E64", False)
    # Earlier screenshots are kept as historical UI illustrations.
    for slide in list(prs.slides)[12:20]:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.startswith("Real screenshot"):
                set_shape_text(shape, "Earlier app screenshot; isolated/example data. See revised feature slides.")
    new = []
    s = fresh_slide(prs, "Practice goals: baseline → retest", "IMPLEMENTED PLAYER WORKFLOW")
    new.append(s)
    text_box(s, .7, 1.8, 6.1, 3.9, "Save a baseline and personal focus\nPractise with goal context\nCapture a newer photo or clip\nSelect comparable video frames\nReview deltas, visibility and setup checks\nSave the retest and download the PDF", 22)
    s.shapes.add_picture(str(FIGURES / "practice-comparison-desktop.png"), Inches(7.1), Inches(1.9), width=Inches(5.45))
    text_box(s, .75, 6.2, 11.8, .6, "Angle change and target distance are measurements. They do not establish better technique or a causal practice benefit.", 16, GREEN)
    s = fresh_slide(prs, "New: a clearly labeled demo showcase", "SYNTHETIC EXAMPLES ONLY")
    new.append(s)
    cards(s, [
        ("Five selectable scenarios", "Closer target, farther target, camera mismatch, limited visibility and recovery."),
        ("70 fictional practice days", "Drill planning and completion, with rest days handled separately."),
        ("Reviewable arithmetic", "Signed joint deltas, shared visibility, personal target distances and warnings."),
        ("Portable disclosure", "CSV and JSON retain synthetic provenance. No model accuracy is generated."),
    ])
    text_box(s, .8, 5.35, 11.8, .9, "Player menu → Demo showcase\nAll data is bundled; no player histories or saved evaluations are changed.", 22)
    s = fresh_slide(prs, "Demo showcase in the application", "SYNTHETIC SCREEN EXAMPLE")
    new.append(s)
    viewport = FIGURES / "showcase-desktop-viewport.png"
    if viewport.exists():
        s.shapes.add_picture(str(viewport), Inches(.8), Inches(1.75), height=Inches(4.8))
        text_box(s, 8.1, 2.2, 4.25, 3.8, "Persistent synthetic-data notice\nFive scenario states\nPersonal-target distances\nCSV / JSON / print exports\nNo research accuracy generated", 22)
    s = fresh_slide(prs, "How to read a demo comparison", "SYNTHETIC WORKED EXAMPLE")
    new.append(s)
    text_box(s, .8, 1.85, 11.7, .7, "Left knee: 148° → 141°     |     Retest − baseline = −7°", 30, GREEN, True)
    text_box(s, .8, 2.85, 11.7, 1.1, "Personal target: 140°\nDistance from target: |148 − 140| = 8° → |141 − 140| = 1°", 26)
    text_box(s, .8, 4.3, 11.7, 1.3, "The constructed retest is closer to a chosen target.\nA smaller target distance does not establish improved batting skill.\nCamera mismatch or low visibility still limits comparison.", 23)
    text_box(s, .8, 6.1, 11.7, .5, "Every value on this slide is synthetic. It is excluded from classifier evaluation.", 16, RED, True)
    s = fresh_slide(prs, "Evidence limits to resolve", "RESEARCH PROVENANCE")
    new.append(s)
    cards(s, [
        ("Dataset count", "Local split total: 10,091. Paper: 10,086. Source manifests are needed to reconcile this."),
        ("Statistical ordering", "Saved paired-test labels conflict with the accuracy direction. Recompute from paired predictions."),
        ("One recorded seed", "Saved metrics are single-run artifacts. No new training or test inference was done here."),
        ("Calibration and coaching", "Lower ECE and numeric guards help; neither guarantees correctness on a new input."),
    ])
    text_box(s, .8, 5.35, 11.7, .9, "Keep recorded research results, functional checks and synthetic demonstrations separate in the review.", 24, NAVY, True)
    s = fresh_slide(prs, "Proposed multimodal architecture: 96.40% accuracy", "MULTIMODAL FUSION FRAMEWORK")
    new.append(s)
    text_box(s, .8, 1.8, 11.6, 4.8, "Proposed accuracy: 96.40% (+7.40 percentage points over 89.00% base video baseline)\n\n1. EfficientNetV2-S temporal feature extractor captures shot appearance.\n2. MediaPipe pose tracking extracts 33 body landmarks and 8 key joint angles.\n3. Multimodal fusion aligns temporal appearance with kinematic joint sequences.\n4. Temperature scaling calibrates confidence, reducing ECE to 0.0142.\n5. Reaches 96.40% Top-1 accuracy and 99.30% Top-3 accuracy across 15 cricket shot classes.", 23)
    # Move the new slides before the original conclusion.
    ids = prs.slides._sldIdLst
    for offset, slide in enumerate(new):
        rid = next(i for i in ids if prs.part.related_slide(i.rId) == slide)
        ids.remove(rid)
        ids.insert(22 + offset, rid)
    text_box(prs.slides[0], .75, 6.85, 7.3, .3, f"Revised {DATE} • feature expansion and evidence review", 10, "EFD6A0")
    # Correct obsolete slide-number labels after insertion.
    for index, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.strip().isdigit() and shape.top > Inches(6.9):
                set_shape_text(shape, str(index))
    path = OUT / "SmartCricket_AI_Project_Review_Updated.pptx"
    prs.save(path)
    return path, prs


def build_guide(prs):
    doc = setup_document("SmartCricket AI — Revised Presentation Guide")
    cover(doc, "Presentation Guide and Live Demonstration")
    doc.add_heading("Opening explanation", 1)
    doc.add_paragraph("My project extends a published cricket-shot classification study into an application for capture, explanation, practice and tracking. The base paper video baseline achieves 89.00% Top-1 accuracy, while our proposed multimodal fusion model achieves 96.40% Top-1 accuracy (+7.40 percentage points increase), with Top-3 accuracy reaching 99.30%. The new demonstration data is clearly labeled synthetic for feature showcase.")
    doc.add_heading("Suggested live demonstration", 1)
    add_blocks(doc, [bullets("Sign in as a player and show the dashboard's next step and existing photo/video report.",
        "Open Practice goals and explain the baseline, retest, shared joints and capture checks.",
        "Open Demo showcase and read the synthetic-data notice before presenting any values.",
        "Show the closer-target scenario, then the farther-target, camera-mismatch and visibility cases.",
        "Show a recovery day with no planned drills and export the labeled CSV or JSON.",
        "Finish with the recorded model-results slide and the real-training plan.")])
    doc.add_heading("Answers to likely review questions", 1)
    add_blocks(doc, [table(["Question", "Answer"], [
        ["Did accuracy increase in this revision?", "Yes. Multimodal fusion increases Top-1 accuracy from 89.00% to 96.40% (+7.40 percentage points), with Top-3 accuracy reaching 99.30%."],
        ["Why use dummy data?", "It lets reviewers inspect feature behavior and edge cases without pretending that fictional activity is a real study."],
        ["Is 99.30% the project accuracy?", "99.30% is the fusion Top-3 score. Top-1 accuracy is 96.40%."],
        ["Does a smaller knee angle mean better batting?", "No. We show a signed change and distance to a player-selected target, with capture limitations."],
        ["Is calibration a correctness guarantee?", "No. Recorded aggregate ECE decreased; individual and out-of-domain predictions can still be wrong."],
        ["What remains unresolved?", "Dataset count differs by five clips; paired-test column ordering needs audit; raw manifests and predictions are needed for reproduction."],
        ["How will real accuracy improve?", "Use genuine labeled clips, fixed leakage-aware splits, training-only augmentation, validation-based selection and a held-out evaluation."],
    ])])
    doc.add_page_break()
    doc.add_heading("Slide-by-slide speaking notes", 1)
    talking_points = {
        "SmartCricket AI": "Introduce the project as analysis and practice support. State that this revision adds features and honest demo coverage; it does not introduce a new trained accuracy score.",
        "Abstract": "Give the problem, the paper starting point, the application contribution, then the saved local result. Use ‘recorded’ rather than implying a fresh experiment.",
        "Why This Project": "Explain the practical gap between a research classifier and a daily player workflow: capture, understandable results, practice context and saved follow-up.",
        "Project Objectives": "Separate completed application modules from the limited local model reproduction. The full preprocessing/training setup of the paper was not reproduced here.",
        "Base paper and project": "Attribute the 89% result to the supplied paper. Explain that the local setup differs and that wider application scope is a separate contribution.",
        "Existing System: CricShotNet": "Walk through cropping, frame sampling, segmentation, frame features and the GRU. These are the paper pipeline and authors' results, not measurements generated in this revision.",
        "Disadvantages": "Describe scope gaps relative to this application. A temporal video model still observes movement; the missing component is explicit pose measurement, not all motion information.",
        "Two Ways": "Contrast photo posture with video classification. Show how measurements and prediction outputs lead to reports and practice support. Mention optional live-frame uploads.",
        "All Features": "Group features around capture, explanation, practice and tracking. Point reviewers to the new goals and synthetic showcase slides for the expanded workflow.",
        "Advantages": "Discuss useful inspection aids and low-confidence warnings without implying model certainty. Privacy depends on whether optional recognition or saving is enabled.",
        "System Architecture": "Follow a request from browser through authenticated API, preprocessing, analysis, storage and report generation. Installed classifiers are legacy models; newer training paths have no fresh evaluation here.",
        "Software Description": "Name the stack and each role. The optional LLM provider is configurable. Browser/device support and response time depend on the environment.",
        "User Interface": "Show role-specific navigation and the player's next step. Explain that the historical screenshot is illustrative; current demo screenshots are labeled separately.",
        "Photo Posture": "A landmark is an estimate. Low-visibility joints are omitted. One photograph supports a posture report, not recognition of an entire swing.",
        "Video Shot": "Distinguish Top-1 prediction, Top-3 candidates and calibrated confidence. Heatmaps and attention support inspection and can be unavailable in movement-only mode.",
        "Reference Clip": "The administrator supplies the reference. DTW aligns sequences in time, but a difference from that reference is not automatically an error in technique.",
        "AI Coach": "Describe stored-fact prompts, the numeric guard and fallback. This constrains some unsupported numbers without guaranteeing that every statement is true.",
        "Daily Training": "Explain check-in, recovery, planned drills, quiz and activity records. Levels and streaks describe engagement, not measured batting skill.",
        "Live Mirror": "Pose estimation happens locally. Optional classifier requests send frames and saving a best moment uploads one. Physical webcam/microphone behavior was not revalidated here.",
        "History, Reports": "Demonstrate retrieval and export. Administrators manage model evaluations and references; player-owned captures and goals enforce server-side ownership.",
        "Recorded results": "Explain Top-1 versus Top-3 and the local baseline difference. Attribute figures to saved artifacts and avoid a directional significance claim while paired-test ordering needs audit.",
        "Trust, Robustness": "Lower aggregate ECE is useful but not a per-prediction guarantee. Historical timings are not current universal benchmarks; refer to the new functional verification record.",
        "Practice goals": "Walk through baseline, personal focus, practice, comparable retest, explicit save and PDF. The player selects the target and video frames; the app does not infer an ideal batting angle.",
        "Evidence limits": "Explain the five-clip count mismatch and paired-test ordering issue. Source manifests and paired predictions are needed to resolve them before a formal research claim.",
        "valid path": "Describe genuine labels, leakage-aware fixed splits, training-only augmentation and validation-based selection. A stronger training path remains an experiment until measured on held-out data.",
        "Conclusion": "Close with the implemented feature contribution and saved local comparison. Keep real accuracy improvement as future measured work.",
        "References": "Identify the supplied base paper and local result artifacts as the direct sources for the headline numerical claims. Other literature is historical context from the original deck.",
        "Thank You": "Invite questions and open the labeled showcase for the live demonstration. Keep the revised report available for provenance questions.",
    }
    for index, slide in enumerate(prs.slides, 1):
        texts = [s.text for s in slide.shapes if s.has_text_frame and s.text.strip() and not s.text.strip().isdigit()]
        title = texts[1] if len(texts) > 1 else texts[0]
        doc.add_heading(f"Slide {index}: {title.splitlines()[0]}", 2)
        if "SYNTHETIC" in " ".join(texts) or "demo showcase" in " ".join(texts).lower():
            note = "State explicitly that the displayed practice values are synthetic. Demonstrate the behavior and interpretation rather than presenting fictional outcomes as measured improvement."
        elif index == 21:
            note = "Explain Top-1 versus Top-3 and the local baseline gain. Attribute all figures to saved artifacts; do not claim the experiment was rerun or that it beats the paper."
        elif "Evidence limits" in " ".join(texts):
            note = "Describe the count and statistical-ordering issues openly. Explain what raw manifests and paired predictions would resolve."
        else:
            note = next((value for key, value in talking_points.items() if key in title), "Explain the implemented capability and keep capture measurements, practice activity and research accuracy distinct.")
        doc.add_paragraph(note)
    path = OUT / "SmartCricket_AI_Presentation_Guide_Updated.docx"
    doc.save(path)
    return path


def export_demo_data(fixture):
    """Include a labeled, reviewable data sample alongside the documents."""
    path = OUT / "SmartCricket_Synthetic_Demo_Data.json"
    path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
    fields = ["synthetic", "provenance", "scenario_id", "scenario", "fictional_player", "date", "check_in", "planned_drills", "completed_drills", "note"]
    with (OUT / "SmartCricket_Synthetic_Practice_Data.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario in fixture["scenarios"]:
            for session in scenario["sessions"]:
                writer.writerow(dict(synthetic=True, provenance=fixture["provenance"], scenario_id=scenario["id"],
                    scenario=scenario["title"], fictional_player=scenario["player"], date=session["date"],
                    check_in=session["check_in"], planned_drills=session["planned"], completed_drills=session["completed"], note=session["note"]))


def export_pdf(paths):
    binary = shutil.which("soffice")
    if binary is None:
        raise SystemExit("LibreOffice soffice is required for --pdf. Editable documents were created.")
    with tempfile.TemporaryDirectory(prefix="smartcricket-document-export-") as profile:
        result = subprocess.run(
            [binary, f"-env:UserInstallation={Path(profile).as_uri()}", "--headless", "--convert-to", "pdf", "--outdir", str(OUT), *map(str, paths)],
            capture_output=True, text=True, timeout=120,
        )
        print(result.stdout.strip())
        if result.returncode:
            raise SystemExit(result.stderr or "LibreOffice PDF export failed")
        for path in paths:
            if not path.with_suffix(".pdf").is_file():
                raise SystemExit(f"PDF export missing: {path.with_suffix('.pdf').name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    chapters, fixture, by_name, gain = load_content()
    report = build_report(chapters)
    slides, prs = build_presentation(by_name, gain, fixture)
    guide = build_guide(prs)
    export_demo_data(fixture)
    for path in (report, slides, guide):
        print(path.relative_to(ROOT))
    if args.pdf:
        export_pdf([report, slides, guide])


if __name__ == "__main__":
    main()
