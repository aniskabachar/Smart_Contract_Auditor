import json, random
from pathlib import Path
from auditor.models import Observation, Action
from auditor.grader import grade
from auditor.reward import compute_reward

DIFFICULTY_HINTS = {
    "easy":   "This contract has exactly ONE vulnerability. Find only that one.",
    "medium": "This contract has TWO vulnerabilities. Find both, no more.",
    "hard":   "This contract has multiple complex vulnerabilities. Be thorough but precise."
}

class SmartContractAuditorEnv:
    def __init__(self, difficulty: str = "easy"):
        self.difficulty       = difficulty
        self.current_contract = None
        self.ground_truth     = None
        self.attempt_number   = 0
        self.done             = False
        self._load_tasks()

    def _load_tasks(self):
        task_dir = Path(f"tasks/{self.difficulty}")
        all_sols = list(task_dir.glob("*.sol"))

        self.ground_truths = {}
        for sol in all_sols:
            json_path = sol.with_suffix(".json")
            if json_path.exists():
                self.ground_truths[sol.stem] = json.load(open(json_path))

        self.contracts = [s for s in all_sols if s.stem in self.ground_truths]

        if not self.contracts:
            raise RuntimeError(f"No contracts found in tasks/{self.difficulty}/")

    def reset(self) -> Observation:
        contract_file         = random.choice(self.contracts)
        self.current_contract = contract_file.read_text()
        self.ground_truth     = self.ground_truths[contract_file.stem]
        self.attempt_number   = 0
        self.done             = False

        return Observation(
            contract_code  = self.current_contract,
            task_level     = self.difficulty,
            context        = DIFFICULTY_HINTS[self.difficulty],
            attempt_number = self.attempt_number
        )

    def step(self, action: Action) -> dict:
        if self.done:
            raise RuntimeError("Episode is done. Call reset() first.")

        self.attempt_number += 1
        grade_result  = grade(action, self.ground_truth)
        reward_value  = compute_reward(grade_result)
        self.done     = True

        return {
            "observation": Observation(
                contract_code  = self.current_contract,
                task_level     = self.difficulty,
                context        = f"Attempt {self.attempt_number} complete.",
                attempt_number = self.attempt_number
            ),
            "reward": reward_value,
            "done":   self.done,
            "info":   grade_result
        }

    def state(self) -> dict:
        return {
            "difficulty":          self.difficulty,
            "attempt_number":      self.attempt_number,
            "done":                self.done,
            "current_contract_id": self.ground_truth.get("contract_id")
                                   if self.ground_truth else None
        }