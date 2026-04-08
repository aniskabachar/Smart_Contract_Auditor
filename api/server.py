import uvicorn
from fastapi import FastAPI, HTTPException

from auditor.benchmark import BENCHMARK_NAME
from auditor.environment import SmartContractAuditorEnv
from auditor.models import Action


app = FastAPI(
    title="Smart Contract Auditor (OpenEnv)",
    description="Deterministic OpenEnv benchmark for Solidity vulnerability auditing.",
    version="2.0.0",
)

envs: dict[str, SmartContractAuditorEnv] = {}

@app.get("/")
def root():
    return {
        "name": BENCHMARK_NAME,
        "version": "2.0.0",
        "description": "Single-domain benchmark for structured smart contract auditing.",
        "endpoints": [
            "/health",
            "/tasks",
            "/reset/{difficulty}",
            "/step/{session_id}",
            "/state/{session_id}",
        ],
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tasks")
def tasks():
    return SmartContractAuditorEnv("easy").list_tasks()

@app.post("/reset/{difficulty}")
def reset(difficulty: str, session_id: str = "default", task_id: str | None = None):
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "difficulty must be: easy | medium | hard")
    try:
        env = SmartContractAuditorEnv(difficulty=difficulty)
        envs[session_id] = env
        return env.reset(task_id=task_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/step/{session_id}")
def step(session_id: str, action: Action):
    if session_id not in envs:
        raise HTTPException(404, "Session not found. Call /reset first.")
    try:
        return envs[session_id].step(action)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get("/state/{session_id}")
def state(session_id: str):
    if session_id not in envs:
        raise HTTPException(404, "Session not found.")
    return envs[session_id].state()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
