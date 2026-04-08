from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from openai import OpenAI

from auditor.benchmark import BENCHMARK_NAME, BENCHMARK_TASK_ORDER
from auditor.models import Action
from client import SmartContractAuditorClient


API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", HF_TOKEN)
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "http://localhost:7860")
ENV_RETRY_ATTEMPTS = int(os.getenv("ENV_RETRY_ATTEMPTS", "3"))
ENV_RETRY_BACKOFF_S = float(os.getenv("ENV_RETRY_BACKOFF_S", "2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.01"))
MAX_SCORE = float(os.getenv("MAX_SCORE", "0.99"))


def _stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _escape_structured_value(value: Any) -> str:
    return str(value).replace("\n", "\\n").replace("\r", "\\r")


def _print_structured_start(task_id: str, env_name: str, model_name: str) -> None:
    print(
        f"[START] task={_escape_structured_value(task_id)} "
        f"env={_escape_structured_value(env_name)} "
        f"model={_escape_structured_value(model_name)}",
        flush=True,
    )


def _print_structured_step(
    step: int,
    action: str,
    reward: float,
    done: bool,
    error: str | None,
) -> None:
    print(
        f"[STEP] step={step} "
        f"action={_escape_structured_value(action)} "
        f"reward={reward:.2f} "
        f"done={str(done).lower()} "
        f"error={_escape_structured_value(error) if error else 'null'}",
        flush=True,
    )


def _print_structured_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    rewards_str = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} "
        f"steps={steps} "
        f"score={score:.2f} "
        f"rewards={rewards_str}",
        flush=True,
    )


def _extract_text(response: Any) -> str:
    message = response.choices[0].message
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        if parts:
            return "".join(parts)
    raise ValueError("Model response did not contain text content.")


def _normalize_score(score: float) -> float:
    if MIN_SCORE >= MAX_SCORE:
        raise ValueError("MIN_SCORE must be less than MAX_SCORE.")
    return min(max(float(score), MIN_SCORE), MAX_SCORE)


def _request_action(client: OpenAI, observation: dict[str, Any]) -> str:
    system_prompt = (
        "You are a Solidity security auditor. "
        "Return only valid JSON with this shape: "
        '{"vulnerabilities":[{"type":"...","location":"...","severity":"low|medium|high|critical","explanation":"..."}]}. '
        "Report only grounded vulnerabilities present in the supplied contract. "
        "Match exact or near-exact line numbers when possible. "
        "Do not add markdown fences or extra commentary."
    )
    user_prompt = (
        f"Task ID: {observation['task_id']}\n"
        f"Difficulty: {observation['task_level']}\n"
        f"Objective: {observation['objective']}\n"
        f"Allowed vulnerability types: {', '.join(observation['allowed_vulnerability_types'])}\n"
        f"Context: {observation['context']}\n\n"
        f"Contract:\n{observation['contract_code']}"
    )

    request_kwargs = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
    }

    try:
        response = client.chat.completions.create(
            response_format={"type": "json_object"},
            **request_kwargs,
        )
        return _extract_text(response)
    except Exception as exc:
        _stderr(
            "JSON-mode request failed; retrying without response_format. "
            f"{type(exc).__name__}: {exc}"
        )

    response = client.chat.completions.create(**request_kwargs)
    return _extract_text(response)


def _normalize_action(raw: str) -> Action:
    payload = json.loads(raw)
    if "vulnerabilities" not in payload or not isinstance(payload["vulnerabilities"], list):
        raise ValueError("Model output must contain a 'vulnerabilities' list.")
    return Action(**payload)


def run_task(
    env: SmartContractAuditorClient,
    client: OpenAI,
    task_id: str,
    difficulty: str,
    session_id: str,
) -> tuple[float, int, list[float], bool]:
    observation = env.reset(difficulty=difficulty, session_id=session_id, task_id=task_id)
    rewards: list[float] = []
    steps = 0

    raw_action = _request_action(client, observation.model_dump())
    action = _normalize_action(raw_action)
    steps += 1
    result = env.step(session_id=session_id, action=action)
    reward = float(result.reward or 0.0)
    rewards.append(reward)
    _print_structured_step(steps, action.model_dump_json(), reward, bool(result.done), None)

    score = _normalize_score(float(result.info.get("grader_score", reward)))
    success = bool(result.done) and score > MIN_SCORE
    return score, steps, rewards, success


def main() -> None:
    if not OPENAI_API_KEY:
        sys.exit("ERROR: Set OPENAI_API_KEY or HF_TOKEN before running inference.py")

    llm_client = OpenAI(api_key=OPENAI_API_KEY, base_url=API_BASE_URL)
    scores: dict[str, float] = {}

    for task_id in BENCHMARK_TASK_ORDER:
        _print_structured_start(task_id, BENCHMARK_NAME, MODEL_NAME)
        score = 0.0
        steps = 0
        rewards: list[float] = []
        success = False

        for attempt in range(1, ENV_RETRY_ATTEMPTS + 1):
            env = SmartContractAuditorClient(HF_SPACE_URL)
            try:
                score, steps, rewards, success = run_task(
                    env=env,
                    client=llm_client,
                    task_id=task_id,
                    difficulty=task_id,
                    session_id=f"benchmark-{task_id}",
                )
                break
            except Exception as exc:
                _stderr(f"Task {task_id} attempt {attempt} failed: {type(exc).__name__}: {exc}")
                if attempt == ENV_RETRY_ATTEMPTS:
                    _print_structured_step(steps + 1, "{}", 0.0, False, str(exc))
                else:
                    time.sleep(ENV_RETRY_BACKOFF_S * attempt)
            finally:
                env.close()

        normalized_score = _normalize_score(score)
        scores[task_id] = round(normalized_score, 4)
        _print_structured_end(success, steps, normalized_score, rewards)

    average = sum(scores.values()) / len(scores)
    _stderr(json.dumps({"scores": scores, "average": round(average, 4)}, sort_keys=True))


if __name__ == "__main__":
    main()
