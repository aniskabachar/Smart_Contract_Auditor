

<div align="center">

# Smart Contract Auditor (OpenEnv)

**An RL-style environment for training and evaluating AI agents on real-world Solidity smart contract security auditing**

[![HuggingFace Space](https://img.shields.io/badge/🤗%20HuggingFace-Space-yellow)](https://huggingface.co/spaces/YOUR_USERNAME/smart-contract-auditor)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/YOUR_USERNAME/smart-contract-auditor)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![OpenEnv](https://img.shields.io/badge/API-OpenEnv%20Compatible-green)](https://openenv.dev)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)

<!-- SCREENSHOT: Add a screenshot of your /docs Swagger UI here -->
<!--![API Docs](assets/docs_screenshot.png) -->

</div>

---

## Overview

**Smart Contract Auditor** is a real-world task simulation environment built on the **OpenEnv API standard**. It models the workflow of a professional Web3 security auditor — an AI agent receives Solidity smart contract source code and must identify security vulnerabilities, classify their severity, and pinpoint their location.

The environment provides step-by-step interaction, continuous reward shaping, and reproducible evaluation — making it suitable for benchmarking LLMs and training RL-based agents on real security tasks.

> **Why this matters:** Smart contract audits cost between $50,000–$500,000 per engagement. Automating vulnerability detection with AI agents has direct, measurable real-world value.

---

## Real-World Task

The agent simulates a **Web3 security auditor** performing the following workflow:

1. Receives a Solidity smart contract as input
2. Analyzes the code for known vulnerability patterns
3. Returns a structured audit report with vulnerability types, locations, severities, and explanations
4. Receives a reward score based on precision, recall, and false positive rate

---

## Environment Architecture

```
┌─────────────────────────────────────────────────────┐
│                  OpenEnv API                        │
│                                                     │
│   POST /reset/{difficulty}  →  Initial Observation  │
│   POST /step/{session_id}   →  Reward + Feedback    │
│   GET  /state/{session_id}  →  Current State        │
└─────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌──────────────────────┐
│  Contract DB    │    │   Grader + Reward     │
│  143 contracts  │    │   Precision/Recall    │
│  Easy/Med/Hard  │    │   F1 + FP Penalty     │
└─────────────────┘    └──────────────────────┘
```

---

## Project Structure

```
smart-contract-auditor/
│
├── auditor/
│   ├── environment.py       # Core OpenEnv class (reset, step, state)
│   ├── models.py            # Pydantic schemas (Action, Observation, Reward)
│   ├── grader.py            # Scoring logic (precision, recall, F1)
│   └── reward.py            # Reward shaping with FP penalties
│
├── agent/
│   └── baseline_agent.py    # LLaMA-3.3-70B baseline via Groq API
│
├── api/
│   └── server.py            # FastAPI server (OpenEnv HTTP interface)
│
├── tasks/
│   ├── easy/                # Single-vulnerability contracts + ground truth
│   ├── medium/              # Two-vulnerability contracts + ground truth
│   └── hard/                # Multi-vulnerability contracts + ground truth
│
├── dataset/                 # SmartBugs Curated raw .sol files
├── parser.py                # Parses SmartBugs → tasks/ with ground truth JSON
├── vulnerabilities.json     # SmartBugs Curated ground truth annotations
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## OpenEnv API

### `POST /reset/{difficulty}`

Starts a new episode. Returns an initial observation.

**Parameters:**
- `difficulty`: `easy` | `medium` | `hard`
- `session_id` (query param, optional): defaults to `"default"`

**Response — Observation:**
```json
{
  "contract_code": "pragma solidity ^0.6.0; contract VulnerableBank { ... }",
  "task_level": "easy",
  "context": "This contract has exactly ONE vulnerability. Find only that one.",
  "attempt_number": 0
}
```

---

### `POST /step/{session_id}`

Agent submits its audit report as an action.

**Request Body — Action:**
```json
{
  "vulnerabilities": [
    {
      "type": "reentrancy",
      "location": "withdraw(), line 14",
      "severity": "critical",
      "explanation": "External call made before state update — classic reentrancy pattern"
    }
  ]
}
```

**Response:**
```json
{
  "observation": { "contract_code": "...", "task_level": "easy", "context": "Attempt 1 complete.", "attempt_number": 1 },
  "reward": 0.85,
  "done": true,
  "info": {
    "score": 0.85,
    "precision": 1.0,
    "recall": 1.0,
    "true_positives": ["reentrancy"],
    "false_positives": [],
    "missed_bugs": []
  }
}
```

---

### `GET /state/{session_id}`

Returns current environment state.

```json
{
  "difficulty": "easy",
  "attempt_number": 1,
  "done": true,
  "current_contract_id": "reentrancy_simple_dao"
}
```

---

## Typed Models (Pydantic)

### `Action`
| Field | Type | Description |
|---|---|---|
| `vulnerabilities` | `List[DetectedVulnerability]` | List of detected bugs |

### `DetectedVulnerability`
| Field | Type | Values |
|---|---|---|
| `type` | `VulnerabilityType` | `reentrancy`, `integer_overflow`, `access_control`, `tx_origin`, `timestamp_dependence`, `selfdestruct`, `uninitialized_storage` |
| `location` | `str` | e.g. `"withdraw(), line 14"` |
| `severity` | `Severity` | `low`, `medium`, `high`, `critical` |
| `explanation` | `str` | Human-readable reason |

### `Observation`
| Field | Type | Description |
|---|---|---|
| `contract_code` | `str` | Full Solidity source code |
| `task_level` | `str` | `easy`, `medium`, or `hard` |
| `context` | `str` | Difficulty hint for the agent |
| `attempt_number` | `int` | Current attempt count |

---

## Observation Space

| Property | Description |
|---|---|
| Type | Text (Solidity source code) |
| Format | Raw `.sol` file content |
| Size | 100 – 6,000 tokens depending on difficulty |
| Metadata | Task level, attempt number, context hint |

---

## Action Space

| Property | Description |
|---|---|
| Type | Structured JSON |
| Schema | List of `DetectedVulnerability` objects |
| Vulnerability types | 7 canonical types |
| Severity levels | 4 levels: low, medium, high, critical |

---

## Reward Function

Rewards are continuous (0.0 → 1.0) and shaped to penalize hallucination:

```python
base_score  = (0.6 × precision) + (0.4 × recall)
fp_penalty  = 0.2 per hallucinated reentrancy/overflow
            + 0.1 per other false positive
final_reward = base_score − fp_penalty − (0.05 × missed_bugs)
```

| Agent Behavior | Reward Effect |
|---|---|
| Correct vulnerability found | +score (via precision/recall) |
| False positive (reentrancy/overflow) | −0.20 |
| False positive (other type) | −0.10 |
| Missed vulnerability | −0.05 |
| Perfect audit | 1.0 |
| All false positives, no true hits | 0.0 |

---

## Task Levels & Dataset

Built on **[SmartBugs Curated](https://github.com/smartbugs/smartbugs-curated)** — 143 annotated real-world Solidity contracts organized by the DASP taxonomy.

| Level | Contracts | Vulnerabilities per Contract | Example |
|---|---|---|---|
| **Easy** | ~90 | Exactly 1 | Single reentrancy in `withdraw()` |
| **Medium** | ~35 | Exactly 2 | Reentrancy + access control |
| **Hard** | ~18 | 3 or more / multi-category | Obfuscated DeFi contract |

### Vulnerability Categories Covered

| Type | Description | Typical Severity |
|---|---|---|
| `reentrancy` | External call before state update | Critical |
| `integer_overflow` | Unchecked arithmetic (Solidity < 0.8) | High |
| `access_control` | Missing `onlyOwner` / auth checks | High |
| `tx_origin` | Auth via `tx.origin` instead of `msg.sender` | Medium |
| `timestamp_dependence` | `block.timestamp` used for randomness/logic | Medium |
| `selfdestruct` | Unprotected `selfdestruct` call | High |
| `uninitialized_storage` | Storage pointer bug | High |

---

## Baseline Agent

The baseline agent uses **LLaMA-3.3-70B** (via Groq API) with a carefully engineered system prompt.

<!-- SCREENSHOT: Add a screenshot of baseline agent terminal output here -->
![Baseline Output](assets/baseline_output.png)

### Baseline Results

| Level | Avg Score | Runs |
|---|---|---|
| **Easy** | 0.60 | 5 |
| **Medium** | 0.30 | 5 |
| **Hard** | 0.34 | 5 |

> Scores show a clear difficulty progression. The primary failure mode is false positives on `reentrancy` and `integer_overflow` in contracts where those bugs are not present.

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Docker (for containerized deployment)
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/smart-contract-auditor
cd smart-contract-auditor

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 4. Parse dataset into task folders
python parser.py

# 5. Run baseline agent
python -m agent.baseline_agent

# 6. Run API server
python api/server.py
# → Visit http://localhost:8000/docs
```

---

## 🐳 Docker

```bash
# Build
docker build -t smart-contract-auditor .

# Run
docker run -p 7860:7860 --env-file .env smart-contract-auditor

# Visit
# http://localhost:7860/docs
```

---

## API Docs (Swagger UI)

When running, visit `/docs` for the interactive Swagger UI where you can test all endpoints directly in the browser.

<!-- SCREENSHOT: Replace the line below with your actual screenshot -->
![Swagger UI](assets/swagger_ui.png)

```
http://localhost:7860/docs         (Docker / HuggingFace)
http://localhost:8000/docs         (Local dev)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Your Groq API key from console.groq.com |

Copy `.env.example` to `.env` and fill in your key:
```
GROQ_API_KEY=your_groq_api_key_here
```

---

## Dataset Citation

This environment uses the **SmartBugs Curated** dataset:

> Ferreira Torres, C. et al. *SmartBugs: A Framework to Analyze Ethereum Smart Contracts*. ICSE 2020.

```bibtex
@inproceedings{ferreira2020smartbugs,
  title     = {SmartBugs: A Framework to Analyze Ethereum Smart Contracts},
  author    = {Ferreira Torres, Christof and others},
  booktitle = {Proceedings of ICSE 2020},
  year      = {2020}
}
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for the **OpenEnv Challenge** · Powered by **SmartBugs Curated** · Agent via **Groq + LLaMA 3.3**

</div>