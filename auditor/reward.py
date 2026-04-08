def compute_reward(grade_result: dict) -> float:
    return round(float(grade_result["grader_score"]), 3)
