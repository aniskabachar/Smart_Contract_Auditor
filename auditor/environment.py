from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from auditor.benchmark import BENCHMARK_TASKS
from auditor.grader import grade
from auditor.models import Action, AuditorState, Observation
from auditor.reward import compute_reward
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata


DIFFICULTY_HINTS = {
    "easy": "This benchmark task has exactly one true finding. Submit only grounded vulnerabilities.",
    "medium": "This benchmark task has exactly two true findings. Avoid duplicate or speculative reports.",
    "hard": "This benchmark task has multiple true findings of the same family. Match type and location carefully.",
}


class SmartContractAuditorEnv(Environment[Action, Observation, AuditorState]):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self, difficulty: str = "easy"):
        super().__init__()
        if difficulty not in BENCHMARK_TASKS:
            raise ValueError(f"Unsupported difficulty: {difficulty}")

        self.difficulty = difficulty
        self.current_contract = None
        self.current_task_id = None
        self.current_contract_id = None
        self.ground_truth = None
        self.attempt_number = 0
        self.done = False
        self._state = AuditorState(
            episode_id=str(uuid4()),
            step_count=0,
            difficulty=difficulty,
            done=False,
        )
        self._load_tasks()

    def _load_tasks(self) -> None:
        self.tasks = {}
        for task_id, benchmark_task in BENCHMARK_TASKS.items():
            task_dir = Path("tasks") / benchmark_task.difficulty
            contract_path = task_dir / f"{benchmark_task.contract_stem}.sol"
            annotation_path = task_dir / f"{benchmark_task.contract_stem}.json"
            if not contract_path.exists() or not annotation_path.exists():
                raise RuntimeError(
                    f"Missing benchmark task assets for {task_id}: "
                    f"{contract_path} / {annotation_path}"
                )

            self.tasks[task_id] = {
                "task_id": task_id,
                "difficulty": benchmark_task.difficulty,
                "contract_path": contract_path,
                "annotation": json.loads(annotation_path.read_text()),
                "objective": benchmark_task.objective,
                "allowed_vulnerability_types": list(benchmark_task.allowed_vulnerability_types),
            }

    def list_tasks(self) -> list[dict]:
        return [
            {
                "task_id": task_id,
                "difficulty": task["difficulty"],
                "contract_id": task["annotation"]["contract_id"],
                "objective": task["objective"],
                "allowed_vulnerability_types": task["allowed_vulnerability_types"],
            }
            for task_id, task in self.tasks.items()
        ]

    def _select_task(self, task_id: str | None) -> dict:
        selected_task_id = task_id or self.difficulty
        if selected_task_id not in self.tasks:
            raise ValueError(f"Unknown task_id: {selected_task_id}")
        return self.tasks[selected_task_id]

    def _initialize_task(
        self,
        task: dict,
        episode_id: str | None = None,
    ) -> None:
        self.difficulty = task["difficulty"]
        self.current_task_id = task["task_id"]
        self.current_contract = task["contract_path"].read_text()
        self.ground_truth = task["annotation"]
        self.current_contract_id = self.ground_truth["contract_id"]
        self.attempt_number = 0
        self.done = False
        self._state = AuditorState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=self.current_task_id,
            contract_id=self.current_contract_id,
            difficulty=self.difficulty,
            done=False,
            info={
                "task_id": self.current_task_id,
                "contract_id": self.current_contract_id,
            },
        )

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        difficulty: str | None = None,
        task_id: str | None = None,
        **kwargs,
    ) -> Observation:
        del seed, kwargs
        if difficulty is not None:
            self.difficulty = difficulty

        task = self._select_task(task_id)
        self._initialize_task(task, episode_id=episode_id)

        return Observation(
            done=False,
            reward=None,
            metadata={
                "task_id": self.current_task_id,
                "contract_id": self.current_contract_id,
                "allowed_vulnerability_types": task["allowed_vulnerability_types"],
            },
            contract_code=self.current_contract,
            task_id=self.current_task_id,
            contract_id=self.current_contract_id,
            task_level=task["difficulty"],
            objective=task["objective"],
            context=DIFFICULTY_HINTS[task["difficulty"]],
            attempt_number=self.attempt_number,
            allowed_vulnerability_types=task["allowed_vulnerability_types"],
            info={
                "task_id": self.current_task_id,
                "contract_id": self.current_contract_id,
                "allowed_vulnerability_types": task["allowed_vulnerability_types"],
            },
        )

    def step(self, action: Action, timeout_s: float | None = None, **kwargs) -> Observation:
        del timeout_s
        if self.done:
            raise RuntimeError("Episode is done. Call reset() first.")
        if self.ground_truth is None:
            metadata = action.metadata or {}
            task_id = kwargs.get("task_id") or metadata.get("task_id")
            difficulty = kwargs.get("difficulty") or metadata.get("difficulty")
            selected_task = None
            if task_id is not None and task_id in self.tasks:
                selected_task = self.tasks[task_id]
            elif difficulty is not None and difficulty in self.tasks:
                selected_task = self.tasks[difficulty]
            elif self.difficulty in self.tasks:
                selected_task = self.tasks[self.difficulty]

            if selected_task is None:
                raise RuntimeError("Environment has not been reset.")

            self._initialize_task(
                selected_task,
                episode_id=kwargs.get("episode_id") or metadata.get("episode_id"),
            )

        self.attempt_number += 1
        grade_result = grade(action, self.ground_truth)
        reward_value = compute_reward(grade_result)
        self.done = True
        self._state.step_count = self.attempt_number
        self._state.done = True
        self._state.task_id = self.current_task_id
        self._state.contract_id = self.current_contract_id
        self._state.difficulty = self.tasks[self.current_task_id]["difficulty"]
        self._state.info = {
            "grader_score": grade_result["grader_score"],
            "task_id": self.current_task_id,
            "contract_id": self.current_contract_id,
        }

        return Observation(
            done=self.done,
            reward=reward_value,
            metadata={
                "grader_score": grade_result["grader_score"],
                "task_id": self.current_task_id,
                "contract_id": self.current_contract_id,
                "allowed_vulnerability_types": self.tasks[self.current_task_id]["allowed_vulnerability_types"],
            },
            contract_code=self.current_contract,
            task_id=self.current_task_id,
            contract_id=self.current_contract_id,
            task_level=self.tasks[self.current_task_id]["difficulty"],
            objective=self.tasks[self.current_task_id]["objective"],
            context="Benchmark submission recorded. Call reset() to start a new task.",
            attempt_number=self.attempt_number,
            allowed_vulnerability_types=self.tasks[self.current_task_id]["allowed_vulnerability_types"],
            info={
                "task_id": self.current_task_id,
                "contract_id": self.current_contract_id,
                "grader_score": grade_result["grader_score"],
                "allowed_vulnerability_types": self.tasks[self.current_task_id]["allowed_vulnerability_types"],
            },
        )

    @property
    def state(self) -> AuditorState:
        self._state.step_count = self.attempt_number
        self._state.task_id = self.current_task_id
        self._state.contract_id = self.current_contract_id
        self._state.difficulty = (
            self.tasks[self.current_task_id]["difficulty"]
            if self.current_task_id
            else self.difficulty
        )
        self._state.done = self.done
        return self._state

    def get_metadata(self) -> EnvironmentMetadata:
        return EnvironmentMetadata(
            name="Smart Contract Auditor",
            description="Deterministic OpenEnv benchmark for structured Solidity smart contract auditing.",
            version="2.0.0",
        )
