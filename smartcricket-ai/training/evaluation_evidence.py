"""Evaluate explicit held-out predictions, with data checks and ordered comparisons.

This module does not train models or read/write application results. Input labels
and model outputs are supplied by the caller. Structural checks cannot establish
that supplied observations are genuine, independently labeled, or untouched by
model selection; the returned evidence retains that limitation.

The default target_accuracy of 0.964 (96.4%) is the *target* accuracy from the
proposed method in the base paper. It is NOT an achieved accuracy of this project.
Claiming "achieved accuracy: 96.4%" requires genuine training on a proper dataset
and evaluation on a held-out test set. Adding dummy data or features cannot
establish that score.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence

SPLITS = frozenset(("train", "val", "test"))


class EvidenceError(ValueError):
    """The supplied observations cannot support this evaluation."""


def _text(value, field: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{context}: {field} must be non-empty text")
    return value.strip()


def _synthetic(value, context: str) -> bool:
    if value is None or value is False or value == "":
        return False
    if value is True:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("false", "0", "no"):
            return False
        if normalized in ("true", "1", "yes", "synthetic", "demo"):
            return True
    raise EvidenceError(f"{context}: synthetic must be true/false, yes/no, or 1/0")


def declared_classes(values: Sequence[str]) -> list[str]:
    if not isinstance(values, (list, tuple)) or len(values) < 2:
        raise EvidenceError("Declare at least two classes in an ordered list")
    classes = [_text(value, "class", "Declared classes") for value in values]
    if len(set(classes)) != len(classes):
        raise EvidenceError("Declared classes must be unique")
    return classes


def validate_manifest(rows: Sequence[Mapping], classes: Sequence[str], *, demo: bool = False) -> dict:
    """Require one clip per row, all three splits, and disjoint supplied groups."""
    if not rows:
        raise EvidenceError("The manifest is empty")
    known = set(classes)
    clips, source_splits, split_counts = {}, {}, Counter()
    has_groups = any(isinstance(row, Mapping) and "source_group" in row for row in rows)
    has_synthetic = False
    for index, row in enumerate(rows, 1):
        context = f"Manifest row {index}"
        if not isinstance(row, Mapping):
            raise EvidenceError(f"{context} must be an object")
        clip = _text(row.get("clip_id"), "clip_id", context)
        label = _text(row.get("true_label"), "true_label", context)
        split = _text(row.get("split"), "split", context)
        if split not in SPLITS:
            raise EvidenceError(f"{context}: split must be train, val, or test")
        if label not in known:
            raise EvidenceError(f"{context}: true_label is not a declared class")
        if clip in clips:
            raise EvidenceError(f"Duplicate clip_id {clip!r}; clip IDs must not overlap within or across splits")
        synthetic = _synthetic(row.get("synthetic"), context)
        has_synthetic |= synthetic
        if synthetic and not demo:
            raise EvidenceError("Synthetic manifest rows require --demo and cannot be research evidence")
        source = None
        if has_groups:
            source = _text(row.get("source_group"), "source_group", context)
            earlier = source_splits.setdefault(source, split)
            if earlier != split:
                raise EvidenceError(f"Source group {source!r} overlaps {earlier} and {split}; split leakage")
        clips[clip] = {"clip_id": clip, "true_label": label, "split": split, "source_group": source}
        split_counts[split] += 1
    if set(split_counts) != SPLITS:
        raise EvidenceError("The complete manifest must include non-empty train, val, and test splits")
    return {"clips": clips, "test": {key: value for key, value in clips.items() if value["split"] == "test"},
            "split_counts": {split: split_counts[split] for split in ("train", "val", "test")},
            "source_group_audit": "passed" if has_groups else "unavailable",
            "source_groups": len(source_splits) if has_groups else None, "synthetic_detected": has_synthetic}


def validate_predictions(rows: Sequence[Mapping], manifest: Mapping, classes: Sequence[str],
                         *, model: str, demo: bool = False) -> list[dict]:
    """Validate exact held-out coverage and optional all-or-none confidence."""
    if not rows:
        raise EvidenceError(f"{model}: predictions are empty")
    test, known, indexed = manifest["test"], set(classes), {}
    confidence_count = 0
    for index, row in enumerate(rows, 1):
        context = f"{model} prediction row {index}"
        if not isinstance(row, Mapping):
            raise EvidenceError(f"{context} must be an object")
        clip = _text(row.get("clip_id"), "clip_id", context)
        actual = _text(row.get("true_label"), "true_label", context)
        predicted = _text(row.get("pred_label"), "pred_label", context)
        if clip in indexed:
            raise EvidenceError(f"{model}: duplicate prediction clip_id {clip!r}")
        if clip not in test:
            raise EvidenceError(f"{model}: clip_id {clip!r} is not in the held-out test split")
        if actual != test[clip]["true_label"]:
            raise EvidenceError(f"{context}: true_label differs from the manifest")
        if actual not in known or predicted not in known:
            raise EvidenceError(f"{context}: labels must belong to the declared classes")
        if row.get("split") not in (None, "", "test"):
            raise EvidenceError(f"{context}: supplied prediction split must be test")
        if row.get("source_group") not in (None, "", test[clip]["source_group"]):
            raise EvidenceError(f"{context}: source_group differs from the manifest")
        if _synthetic(row.get("synthetic"), context) and not demo:
            raise EvidenceError("Synthetic predictions require --demo and cannot be research evidence")
        confidence = row.get("confidence")
        if confidence is None or confidence == "":
            confidence = None
        else:
            if isinstance(confidence, bool):
                raise EvidenceError(f"{context}: confidence must be a finite number between 0 and 1")
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                raise EvidenceError(f"{context}: confidence must be a finite number between 0 and 1") from None
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise EvidenceError(f"{context}: confidence must be a finite number between 0 and 1")
            confidence_count += 1
        indexed[clip] = {"clip_id": clip, "true_label": actual, "pred_label": predicted,
                         "confidence": confidence, "correct": actual == predicted}
    missing = set(test) - set(indexed)
    if missing:
        raise EvidenceError(f"{model}: missing predictions for {len(missing)} held-out test clips")
    if confidence_count not in (0, len(indexed)):
        raise EvidenceError(f"{model}: confidence must be supplied for every prediction or omitted for every prediction")
    return [indexed[clip] for clip in sorted(indexed)]


def wilson_interval(correct: int, total: int) -> dict:
    """Two-sided 95% Wilson interval for a binomial accuracy proportion."""
    if (isinstance(correct, bool) or isinstance(total, bool) or not isinstance(correct, int)
            or not isinstance(total, int) or total <= 0 or not 0 <= correct <= total):
        raise EvidenceError("Wilson interval requires integer 0 <= correct <= total, with total > 0")
    z = 1.959963984540054
    proportion = correct / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return {"method": "Wilson", "confidence_level": 0.95, "lower": max(0.0, centre - radius),
            "upper": min(1.0, centre + radius),
            "interpretation": "Binomial sampling interval only; does not account for source correlation, label error, or model selection."}


def calibration_bins(rows: Sequence[Mapping], bins: int = 10) -> dict:
    """ECE of supplied predicted-class confidence, with explicit bin contents."""
    if isinstance(bins, bool) or not isinstance(bins, int) or not 2 <= bins <= 100:
        raise EvidenceError("Calibration bins must be an integer between 2 and 100")
    if all(row["confidence"] is None for row in rows):
        return {"ece": None, "bins": [], "note": "Predicted-class confidence was not supplied."}
    counts = [0] * bins
    confidence_sums = [0.0] * bins
    correct_sums = [0] * bins
    for row in rows:
        index = min(int(row["confidence"] * bins), bins - 1)
        counts[index] += 1
        confidence_sums[index] += row["confidence"]
        correct_sums[index] += int(row["correct"])
    output, ece = [], 0.0
    for index, count in enumerate(counts):
        accuracy = correct_sums[index] / count if count else None
        confidence = confidence_sums[index] / count if count else None
        gap = abs(accuracy - confidence) if count else None
        if count:
            ece += count / len(rows) * gap
        output.append({"bin": index + 1, "lower": index / bins, "upper": (index + 1) / bins,
                       "upper_inclusive": index == bins - 1, "count": count,
                       "accuracy": accuracy, "mean_confidence": confidence, "absolute_gap": gap})
    return {"ece": ece, "bins": output,
            "note": "ECE uses supplied predicted-class confidence. Empty bins remain null; aggregate ECE is not an individual correctness guarantee."}


def classification_metrics(rows: Sequence[Mapping], classes: Sequence[str], *, model: str, bins: int = 10) -> dict:
    """Compute classification metrics over the full declared class universe."""
    positions = {label: index for index, label in enumerate(classes)}
    matrix = [[0 for _ in classes] for _ in classes]
    for row in rows:
        matrix[positions[row["true_label"]]][positions[row["pred_label"]]] += 1
    per_class = []
    for index, label in enumerate(classes):
        tp = matrix[index][index]
        support = sum(matrix[index])
        predicted = sum(line[index] for line in matrix)
        precision, recall = tp / predicted if predicted else 0.0, tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({"class": label, "support": support, "predicted": predicted, "true_positive": tp,
                          "precision": precision, "recall": recall, "f1": f1})
    total = len(rows)
    correct = sum(matrix[index][index] for index in range(len(classes)))
    calibration = calibration_bins(rows, bins)
    return {"model": model, "test_clips": total, "correct": correct, "top1": correct / total,
            "macro_precision": sum(row["precision"] for row in per_class) / len(classes),
            "macro_recall": sum(row["recall"] for row in per_class) / len(classes),
            "macro_f1": sum(row["f1"] for row in per_class) / len(classes),
            "macro_average_policy": "Every declared class is included; undefined precision/recall/F1 are zero.",
            "accuracy_interval": wilson_interval(correct, total), "ece": calibration["ece"],
            "calibration": calibration, "per_class": per_class,
            "confusion": {"row_axis": "true_label", "column_axis": "pred_label", "classes": list(classes), "counts": matrix}}


def paired_mcnemar(first: Sequence[Mapping], second: Sequence[Mapping], first_model: str, second_model: str) -> dict:
    """Ordered two-sided exact binomial McNemar test on matching clip IDs."""
    second_index = {row["clip_id"]: row for row in second}
    if len(second_index) != len(second) or {row["clip_id"] for row in first} != set(second_index):
        raise EvidenceError("Paired comparison requires identical unique clip IDs")
    if len({row["clip_id"] for row in first}) != len(first):
        raise EvidenceError("Paired comparison requires identical unique clip IDs")
    b = c = both_correct = both_wrong = 0
    for row in first:
        other = second_index[row["clip_id"]]
        if row["true_label"] != other["true_label"]:
            raise EvidenceError("Paired comparison true labels disagree")
        one, two = row["correct"], other["correct"]
        b += int(one and not two)
        c += int(two and not one)
        both_correct += int(one and two)
        both_wrong += int(not one and not two)
    n, lower = b + c, min(b, c)
    if n:
        logs = [math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) - n * math.log(2)
                for k in range(lower + 1)]
        maximum = max(logs)
        log_p = min(0.0, math.log(2) + maximum + math.log(sum(math.exp(value - maximum) for value in logs)))
        p_value = math.exp(log_p)
    else:
        log_p, p_value = 0.0, 1.0
    return {"first_model": first_model, "second_model": second_model,
            "only_first_right": b, "only_second_right": c,
            "both_right": both_correct, "both_wrong": both_wrong,
            "discordant_clips": n, "p_value": p_value, "log_p_value": log_p,
            "p_value_underflow": p_value == 0.0,
            "method": "Two-sided exact binomial McNemar (floating-point log-space calculation)",
            "first_minus_second_accuracy_points": 100 * (b - c) / len(first),
            "interpretation": "Conditional paired-test evidence on these supplied clips; a p-value is not the probability an improvement arose by luck or proof of generalization."}


def build_evidence(manifest_rows: Sequence[Mapping], predictions: Sequence[Mapping], classes: Sequence[str],
                   *, model: str, comparator_predictions: Sequence[Mapping] | None = None,
                   comparator_model: str | None = None, target_accuracy: float = 0.964,
                   bins: int = 10, demo: bool = False) -> dict:
    """Validate all inputs, then produce one self-contained evidence object.

    target_accuracy is 96.4% from the base paper's proposed method. It is a
    *target*, NOT an achieved accuracy. Achieved accuracy requires genuine
    training on a proper dataset and evaluation on a held-out test set.
    Adding dummy data or features cannot establish that score.
    """
    classes = declared_classes(classes)
    model = _text(model, "model", "Evaluation")
    if (isinstance(target_accuracy, bool) or not isinstance(target_accuracy, (int, float))
            or not math.isfinite(target_accuracy) or not 0 < target_accuracy <= 1):
        raise EvidenceError("Target accuracy must be a finite proportion greater than 0 and no more than 1")
    if not isinstance(demo, bool):
        raise EvidenceError("demo must be a boolean")
    manifest = validate_manifest(manifest_rows, classes, demo=demo)
    first = validate_predictions(predictions, manifest, classes, model=model, demo=demo)
    metrics = [classification_metrics(first, classes, model=model, bins=bins)]
    paired = None
    if (comparator_predictions is None) != (comparator_model is None):
        raise EvidenceError("Provide both comparator predictions and comparator model name")
    if comparator_predictions is not None:
        comparator_model = _text(comparator_model, "comparator_model", "Evaluation")
        if comparator_model == model:
            raise EvidenceError("Compared model names must be different")
        second = validate_predictions(comparator_predictions, manifest, classes, model=comparator_model, demo=demo)
        metrics.append(classification_metrics(second, classes, model=comparator_model, bins=bins))
        paired = paired_mcnemar(first, second, model, comparator_model)
    limits = ["Input labels, independence from model selection, and authenticity are caller-supplied and not independently verified.",
              "No source video or near-duplicate content audit is performed; distinct IDs alone cannot rule out duplicate footage.",
              "This is per-clip test evaluation, not a measurement of player skill or application feature quality."]
    if manifest["source_group_audit"] == "unavailable":
        limits.append("Source groups were not supplied; source/match leakage could not be checked.")
    if demo:
        limits.insert(0, "SYNTHETIC DEMONSTRATION ONLY. These metrics are not research evidence or achieved accuracy.")
    targets = []
    for result in metrics:
        targets.append({"model": result["model"], "target_accuracy": target_accuracy,
                        "status": "demo_only_not_achieved_evidence" if demo else (
                            "threshold_reached_on_supplied_test_predictions" if result["top1"] >= target_accuracy else "not_reached"),
                        "remaining_percentage_points": max(0.0, 100 * (target_accuracy - result["top1"]))})
    return {"schema_version": 1, "artifact_type": "held_out_prediction_evidence", "synthetic": demo,
            "research_claim_eligible": not demo, "provenance": (
                "SYNTHETIC DEMONSTRATION DATA — not achieved research accuracy" if demo else
                "Metrics calculated from supplied labeled held-out predictions; authenticity and selection independence remain caller claims"),
            "classes": classes, "manifest_audit": {"split_counts": manifest["split_counts"],
                "total_clips": len(manifest["clips"]), "unique_clip_ids": True,
                "source_group_audit": manifest["source_group_audit"], "source_groups": manifest["source_groups"]},
            "metrics": metrics, "paired_comparison": paired, "targets": targets,
            "paper_context": {"reported_top1": 0.89, "directly_comparable": False,
                "note": "The supplied base paper reports 89% under its own experimental setup. This tool does not reproduce that setup."},
            "limitations": limits}
