# Smart Contract Auditor — OpenEnv

An RL-style environment where AI agents audit Solidity smart contracts
for security vulnerabilities. Built on the OpenEnv API standard.

## What It Does

An AI agent receives Solidity contract code and must identify security
vulnerabilities — reentrancy, integer overflow, access control bugs, etc.
The environment grades the agent and returns a reward score from 0.0 to 1.0.

## Task Levels

| Level  | Description                          | Example                        |
|--------|--------------------------------------|--------------------------------|
| Easy   | Single vulnerability per contract    | One reentrancy bug             |
| Medium | Two vulnerabilities per contract     | Reentrancy + access control    |
| Hard   | Multiple complex vulnerabilities     | Obfuscated multi-bug contracts |

## Action Space
```json
{
  "vulnerabilities": [
    {
      "type": "reentrancy|integer_overflow|access_control|tx_origin|timestamp_dependence|selfdestruct|uninitialized_storage",
      "location": "function name and line number",
      "severity": "low|medium|high|critical",
      "explanation": "reason this is a vulnerability"
    }
  ]
}
```

## Observation Space
```json
{
  "contract_code": "pragma solidity ...",
  "task_level": "easy|medium|hard",
  "context": "instruction hint for the agent",
  "attempt_number": 0
}
```

## Reward

| Outcome              | Effect        |
|----------------------|---------------|
| Correct bug found    | +score        |
| False positive       | -0.2 penalty  |
| Missed bug           | -0.05 penalty |
| Score range          | 0.0 → 1.0     |

## Baseline Results

| Level  | Avg Score |
|--------|-----------|
| Easy   | 0.60      |
| Medium | 0.30      |
| Hard   | 0.34      |

Agent: `llama-3.3-70b-versatile` via Groq API

## Setup
```bash
git clone https://github.com/yourusername/smart-contract-auditor-env
cd smart-contract-auditor-env
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

## Run Baseline Agent
```bash
python -m agent.baseline_agent
```

## Run API Server
```bash
python api/server.py
# Visit http://localhost:8000/docs
```

## Run with Docker
```bash
docker build -t smart-contract-auditor .
docker run -p 8000:8000 --env-file .env smart-contract-auditor
```

## Dataset

Built on [SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated) —
143 annotated Solidity contracts across 3 difficulty levels.