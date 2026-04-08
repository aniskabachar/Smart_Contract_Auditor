from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    difficulty: str
    contract_stem: str
    objective: str
    allowed_vulnerability_types: tuple[str, ...]


BENCHMARK_NAME = "smart_contract_auditor"
BENCHMARK_TASK_ORDER = ("easy", "medium", "hard")
BENCHMARK_TASKS = {
    "easy": BenchmarkTask(
        task_id="easy",
        difficulty="easy",
        contract_stem="reentrancy_simple",
        objective=(
            "Submit one structured audit report for a contract with exactly one "
            "real vulnerability."
        ),
        allowed_vulnerability_types=("reentrancy",),
    ),
    "medium": BenchmarkTask(
        task_id="medium",
        difficulty="medium",
        contract_stem="lotto",
        objective=(
            "Submit one structured audit report for a contract with two unchecked "
            "low-level call findings."
        ),
        allowed_vulnerability_types=("unchecked_calls",),
    ),
    "hard": BenchmarkTask(
        task_id="hard",
        difficulty="hard",
        contract_stem="tokensalechallenge",
        objective=(
            "Submit one structured audit report for a contract with multiple "
            "arithmetic overflow findings."
        ),
        allowed_vulnerability_types=("integer_overflow",),
    ),
}
