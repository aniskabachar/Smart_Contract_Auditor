def grade(prediction, ground_truth: dict) -> dict:
    # Safety check
    if not ground_truth.get("vulnerabilities"):
        return {
            "score": 0.0, "precision": 0.0, "recall": 0.0,
            "true_positives": [], "false_positives": [], "missed_bugs": []
        }

    true_bugs  = {v["type"] for v in ground_truth["vulnerabilities"]}
    found_bugs = {v.type.value for v in prediction.vulnerabilities}

    true_positives  = found_bugs & true_bugs
    false_positives = found_bugs - true_bugs
    false_negatives = true_bugs  - found_bugs

    precision = len(true_positives) / len(found_bugs) if found_bugs else 0
    recall    = len(true_positives) / len(true_bugs)  if true_bugs  else 0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0)

    penalty     = 0.1 * len(false_positives)
    final_score = max(0.0, min(1.0, f1 - penalty))

    return {
        "score":           round(final_score, 3),
        "precision":       round(precision, 3),
        "recall":          round(recall, 3),
        "true_positives":  list(true_positives),
        "false_positives": list(false_positives),
        "missed_bugs":     list(false_negatives)
    }