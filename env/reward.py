def compute_reward(grade_result: dict) -> float:
    score           = grade_result["score"]
    false_positives = len(grade_result["false_positives"])
    missed          = len(grade_result["missed_bugs"])

    reward  = score
    reward -= 0.05 * false_positives
    reward -= 0.05 * missed

    return round(max(0.0, min(1.0, reward)), 3)