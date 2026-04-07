from fastapi import FastAPI, HTTPException
from auditor.environment import SmartContractAuditorEnv
from auditor.models import Action, Observation
import uvicorn

app  = FastAPI(
    title       = "Smart Contract Auditor (OpenEnv)",
    description = "An RL-style environment for AI agents to audit Solidity smart contracts",
    version     = "1.0.0"
)

envs = {}  # session_id → env instance

@app.get("/")
def root():
    return {
        "name":        "Smart Contract Auditor OpenEnv",
        "version":     "1.0.0",
        "description": "RL environment for smart contract vulnerability detection",
        "endpoints":   ["/reset/{difficulty}", "/step/{session_id}", "/state/{session_id}", "/health"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reset/{difficulty}")
def reset(difficulty: str, session_id: str = "default"):
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "difficulty must be: easy | medium | hard")
    envs[session_id] = SmartContractAuditorEnv(difficulty=difficulty)
    return envs[session_id].reset()

@app.post("/step/{session_id}")
def step(session_id: str, action: Action):
    if session_id not in envs:
        raise HTTPException(404, "Session not found. Call /reset first.")
    return envs[session_id].step(action)

@app.get("/state/{session_id}")
def state(session_id: str):
    if session_id not in envs:
        raise HTTPException(404, "Session not found.")
    return envs[session_id].state()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)