from __future__ import annotations

import re
from typing import Any


LINE_NUMBER_PATTERN = re.compile(r"\d+")


def _extract_line_numbers(location: str) -> tuple[int, ...]:
    if not location:
        return ()
    return tuple(sorted({int(value) for value in LINE_NUMBER_PATTERN.findall(location)}))


def _line_distance(left: tuple[int, ...], right: tuple[int, ...]) -> int | None:
    if not left or not right:
        return None
    return min(abs(a - b) for a in left for b in right)


def _candidate_match_score(predicted: dict[str, Any], actual: dict[str, Any]) -> float:
    if predicted["type"] != actual["type"]:
        return 0.0

    predicted_lines = predicted["lines"]
    actual_lines = actual["lines"]

    if predicted_lines and actual_lines:
        if set(predicted_lines) == set(actual_lines):
            return 1.0
        if set(predicted_lines) & set(actual_lines):
            return 1.0

        distance = _line_distance(predicted_lines, actual_lines)
        if distance is not None and distance <= 2:
            return 0.85
        return 0.45

    if not predicted_lines and not actual_lines:
        return 0.7

    return 0.55


def _normalize_prediction(prediction) -> tuple[list[dict[str, Any]], int]:
    normalized = []
    malformed = 0
    for item in prediction.vulnerabilities:
        vulnerability_type = getattr(item.type, "value", str(item.type))
        location = (item.location or "").strip()
        explanation = (item.explanation or "").strip()

        if not vulnerability_type or not explanation:
            malformed += 1

        normalized.append(
            {
                "type": vulnerability_type,
                "location": location,
                "lines": _extract_line_numbers(location),
            }
        )
    return normalized, malformed


def _normalize_ground_truth(ground_truth: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": vulnerability["type"],
            "location": vulnerability["location"],
            "lines": _extract_line_numbers(vulnerability["location"]),
        }
        for vulnerability in ground_truth.get("vulnerabilities", [])
    ]


def grade(prediction, ground_truth: dict[str, Any]) -> dict[str, Any]:
    actual_findings = _normalize_ground_truth(ground_truth)
    predicted_findings, malformed_predictions = _normalize_prediction(prediction)

    if not actual_findings:
        return {
            "grader_score": 0.0,
            "matched_findings": [],
            "partial_matches": [],
            "unmatched_predictions": predicted_findings,
            "missed_findings": [],
            "malformed_predictions": malformed_predictions,
            "duplicate_predictions": 0,
            "precision": 0.0,
            "recall": 0.0,
        }

    seen_signatures: set[tuple[str, str]] = set()
    duplicate_predictions = 0
    for finding in predicted_findings:
        signature = (finding["type"], finding["location"])
        if signature in seen_signatures:
            duplicate_predictions += 1
        else:
            seen_signatures.add(signature)

    candidates: list[tuple[float, int, int]] = []
    for predicted_index, predicted in enumerate(predicted_findings):
        for actual_index, actual in enumerate(actual_findings):
            score = _candidate_match_score(predicted, actual)
            if score > 0:
                candidates.append((score, predicted_index, actual_index))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    used_predictions: set[int] = set()
    used_actuals: set[int] = set()
    matched_findings = []
    partial_matches = []
    total_match_score = 0.0

    for score, predicted_index, actual_index in candidates:
        if predicted_index in used_predictions or actual_index in used_actuals:
            continue

        used_predictions.add(predicted_index)
        used_actuals.add(actual_index)
        total_match_score += score

        match_record = {
            "prediction": predicted_findings[predicted_index],
            "ground_truth": actual_findings[actual_index],
            "match_score": round(score, 3),
        }
        if score >= 1.0:
            matched_findings.append(match_record)
        else:
            partial_matches.append(match_record)

    unmatched_predictions = [
        predicted_findings[index]
        for index in range(len(predicted_findings))
        if index not in used_predictions
    ]
    missed_findings = [
        actual_findings[index]
        for index in range(len(actual_findings))
        if index not in used_actuals
    ]

    precision = total_match_score / len(predicted_findings) if predicted_findings else 0.0
    recall = total_match_score / len(actual_findings)

    penalty = (
        0.12 * len(unmatched_predictions)
        + 0.08 * duplicate_predictions
        + 0.05 * malformed_predictions
    )
    grader_score = max(0.0, min(1.0, recall - penalty))

    return {
        "grader_score": round(grader_score, 3),
        "matched_findings": matched_findings,
        "partial_matches": partial_matches,
        "unmatched_predictions": unmatched_predictions,
        "missed_findings": missed_findings,
        "malformed_predictions": malformed_predictions,
        "duplicate_predictions": duplicate_predictions,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
    }
