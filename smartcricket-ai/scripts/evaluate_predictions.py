"""Create evidence from explicit held-out predictions, without changing old results.

Example:
    python scripts/evaluate_predictions.py --manifest split.csv \
      --classes classes.json --predictions fusion.csv --model fusion \
      --compare-predictions video.csv --compare-model video \
      --output-dir experiments/evaluation-001

Use --demo for explicitly synthetic examples. Such output is prominently labeled
and never counts as achieved research accuracy, even if its toy score is high.

The default --target-accuracy of 0.964 (96.4%) is a *target* from the base paper's
proposed method, NOT an achieved accuracy of this project. Claiming achieved
accuracy requires genuine training and held-out test evaluation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from training.evaluation_evidence import EvidenceError, build_evidence  # noqa: E402

MAX_INPUT_BYTES = 64 * 1024 * 1024
PROTECTED = (APP / "data/results", APP / "models", ROOT / "deliverables", ROOT / ".git")


def input_bytes(path: Path, role: str) -> tuple[bytes, dict]:
    if not path.is_file():
        raise EvidenceError(f"{role}: input file does not exist: {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise EvidenceError(f"{role}: input file is larger than 64 MB")
    content = path.read_bytes()
    return content, {"role": role, "path": str(path.resolve()), "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest()}


def read_csv(path: Path, role: str, required: set[str]) -> tuple[list[dict], dict]:
    content, provenance = input_bytes(path, role)
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
        fields = reader.fieldnames
        if (not fields or len(fields) != len(set(fields)) or any(not field for field in fields)
                or not required.issubset(fields)):
            raise EvidenceError(f"{role}: CSV needs unique headers including {', '.join(sorted(required))}")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise EvidenceError(f"{role}: unreadable UTF-8 CSV: {exc}") from None
    if any(None in row for row in rows):
        raise EvidenceError(f"{role}: a row has more cells than the CSV header")
    return rows, provenance


def checked_output(path: Path) -> Path:
    destination = path.resolve()
    for protected in PROTECTED:
        protected = protected.resolve()
        if destination == protected or protected in destination.parents:
            raise EvidenceError(f"Choose a new experiment directory outside protected artifacts: {protected}")
    if destination.exists():
        raise EvidenceError(f"Output directory already exists; existing files will not be replaced: {destination}")
    return destination


def spreadsheet_value(value):
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def write_csv(path: Path, fields: list[str], rows: list[dict], synthetic: bool, provenance: str):
    # Every row remains labeled when a table is detached from the evidence JSON.
    fields = ["synthetic", "provenance", *fields]
    with path.open("x", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            combined = {"synthetic": synthetic, "provenance": provenance, **row}
            writer.writerow({key: spreadsheet_value(combined.get(key)) for key in fields})


def write_evidence(destination: Path, evidence: dict):
    # mkdir is the no-overwrite boundary, including a directory created by
    # another process after checked_output returned.
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "evaluation_evidence.json").open("x", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    synthetic, provenance = evidence["synthetic"], evidence["provenance"]
    write_csv(destination / "model_metrics.csv", ["model", "test_clips", "correct", "top1", "macro_precision",
              "macro_recall", "macro_f1", "ece"], evidence["metrics"], synthetic, provenance)
    per_class, confusion, bins = [], [], []
    for model in evidence["metrics"]:
        per_class.extend({"model": model["model"], **row} for row in model["per_class"])
        bins.extend({"model": model["model"], **row} for row in model["calibration"]["bins"])
        labels = model["confusion"]["classes"]
        for true_index, actual in enumerate(labels):
            for pred_index, predicted in enumerate(labels):
                confusion.append({"model": model["model"], "true_label": actual, "pred_label": predicted,
                                  "count": model["confusion"]["counts"][true_index][pred_index]})
    write_csv(destination / "per_class.csv", ["model", "class", "support", "predicted", "true_positive", "precision", "recall", "f1"], per_class, synthetic, provenance)
    write_csv(destination / "confusion.csv", ["model", "true_label", "pred_label", "count"], confusion, synthetic, provenance)
    write_csv(destination / "calibration.csv", ["model", "bin", "lower", "upper", "upper_inclusive", "count", "accuracy", "mean_confidence", "absolute_gap"], bins, synthetic, provenance)
    paired = evidence["paired_comparison"]
    if paired is not None:
        write_csv(destination / "paired_comparison.csv", ["first_model", "second_model", "only_first_right",
                  "only_second_right", "both_right", "both_wrong", "discordant_clips", "p_value", "log_p_value",
                  "p_value_underflow", "first_minus_second_accuracy_points", "method", "interpretation"], [paired], synthetic, provenance)
    (destination / "README.txt").write_text(
        evidence["provenance"] + "\n\n" + "\n".join(evidence["limitations"]) +
        "\n\nValues in CSV files are proportions, not percentages, unless a field explicitly says points. "
        "This evidence format is intentionally separate from the older training summary.json import.\n",
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--classes", type=Path, required=True, help="JSON ordered list of all declared class names")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--compare-predictions", type=Path)
    parser.add_argument("--compare-model")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-accuracy", type=float, default=.964, help="Proposed target proportion (default 0.964); this is NOT achieved accuracy — it requires genuine training and held-out test evaluation")
    parser.add_argument("--calibration-bins", type=int, default=10)
    parser.add_argument("--demo", action="store_true", help="Allow synthetic examples and label output ineligible as research evidence")
    args = parser.parse_args(argv)
    try:
        destination = checked_output(args.output_dir)
        if (args.compare_predictions is None) != (args.compare_model is None):
            raise EvidenceError("Provide --compare-predictions and --compare-model together")
        manifest, source = read_csv(args.manifest, "manifest", {"clip_id", "true_label", "split"})
        inputs = [source]
        predictions, source = read_csv(args.predictions, "predictions", {"clip_id", "true_label", "pred_label"})
        inputs.append(source)
        content, source = input_bytes(args.classes, "classes")
        inputs.append(source)
        try:
            classes = json.loads(content)
        except (ValueError, UnicodeError):
            raise EvidenceError("classes: expected a UTF-8 JSON ordered list of class names") from None
        comparator = None
        if args.compare_predictions is not None:
            comparator, source = read_csv(args.compare_predictions, "comparator_predictions", {"clip_id", "true_label", "pred_label"})
            inputs.append(source)
        evidence = build_evidence(manifest, predictions, classes, model=args.model,
            comparator_predictions=comparator, comparator_model=args.compare_model,
            target_accuracy=args.target_accuracy, bins=args.calibration_bins, demo=args.demo)
        evidence["input_files"] = inputs
        evidence["generated_at"] = datetime.now(timezone.utc).isoformat()
        write_evidence(destination, evidence)
    except (EvidenceError, OSError) as exc:
        parser.exit(2, f"Evaluation refused: {exc}\n")
    print(evidence["provenance"])
    for model in evidence["metrics"]:
        print(f"{model['model']}: {model['correct']}/{model['test_clips']} supplied clips correct; "
              f"Top-1 {100 * model['top1']:.2f}%; macro-F1 {100 * model['macro_f1']:.2f}%")
    print(f"Evidence written to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
