def compute_reward(grade_result: dict) -> float:
    precision       = grade_result["precision"]
    recall          = grade_result["recall"]
    false_positives = grade_result["false_positives"]
    missed          = len(grade_result["missed_bugs"])

    base = (0.6 * precision) + (0.4 * recall)

    # Extra penalty for commonly hallucinated types
    HALLUCINATION_PRONE = {"reentrancy", "integer_overflow"}
    fp_penalty = sum(
        0.2 if fp in HALLUCINATION_PRONE else 0.1
        for fp in false_positives
    )

    reward = base - fp_penalty - (0.05 * missed)
    return round(max(0.0, min(1.0, reward)), 3)