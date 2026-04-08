from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from auditor.models import Action, AuditorState, Observation, StepResult


class SmartContractAuditorClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._session_tasks: dict[str, dict[str, str]] = {}

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            filtered = {key: value for key, value in query.items() if value is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered)}"

        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url=url, data=body, headers=headers, method=method)
        try:
            with urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{exc.code} {exc.reason}: {detail}") from exc

    def reset(
        self,
        difficulty: str,
        session_id: str = "default",
        task_id: str | None = None,
    ) -> Observation:
        data = self._request(
            "POST",
            "/reset",
            payload={
                "difficulty": difficulty,
                "task_id": task_id,
                "episode_id": session_id,
            },
        )
        resolved_task_id = data["observation"].get("task_id", task_id or difficulty)
        self._session_tasks[session_id] = {
            "difficulty": difficulty,
            "task_id": resolved_task_id,
        }
        return Observation(**data["observation"])

    def step(self, session_id: str, action: Action) -> StepResult:
        session_task = self._session_tasks.get(session_id, {})
        action_payload = action.model_dump()
        action_payload["metadata"] = {
            **action_payload.get("metadata", {}),
            "difficulty": session_task.get("difficulty"),
            "task_id": session_task.get("task_id"),
            "episode_id": session_id,
        }
        data = self._request(
            "POST",
            "/step",
            payload={
                "action": action_payload,
                "request_id": session_id,
                "difficulty": session_task.get("difficulty"),
                "task_id": session_task.get("task_id"),
                "episode_id": session_id,
            },
        )
        return StepResult(
            observation=Observation(**data["observation"]),
            reward=float(data.get("reward") or 0.0),
            done=bool(data.get("done")),
            info=dict(data["observation"].get("info") or {}),
        )

    def state(self, session_id: str = "default") -> AuditorState:
        data = self._request("GET", "/state", query={"episode_id": session_id})
        return AuditorState(**data)

    def close(self) -> None:
        return None
