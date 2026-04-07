import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from auditor.environment import SmartContractAuditorEnv
from auditor.models import Action

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a precise Solidity smart contract auditor.
Your job is to find ONLY vulnerabilities that are CLEARLY present in the code.

STRICT RULES:
- Only report a vulnerability if you can point to the EXACT line causing it
- Do NOT guess or speculate
- Do NOT report vulnerabilities that might exist — only ones that DO exist
- It is better to report fewer bugs than to report false positives
- If you are not 100% sure, do NOT include it
- Do NOT default to reentrancy unless you see a clear external call before state update
- access_control bugs are missing modifiers like onlyOwner or auth checks
- integer_overflow is unchecked arithmetic in Solidity < 0.8.0
- Always check what Solidity version is used (pragma) before deciding bug type

Respond ONLY in this exact JSON format with no extra text:
{
  "vulnerabilities": [
    {
      "type": "reentrancy|integer_overflow|access_control|tx_origin|timestamp_dependence|selfdestruct|uninitialized_storage",
      "location": "function name and line number",
      "severity": "low|medium|high|critical",
      "explanation": "exact line and reason why this is a vulnerability"
    }
  ]
}"""

VALID_TYPES = {
    "reentrancy", "integer_overflow", "access_control", "tx_origin",
    "timestamp_dependence", "selfdestruct", "uninitialized_storage",
    "bad_randomness", "denial_of_service", "front_running",
    "unchecked_calls", "short_address", "other"
}

# Add this constant at the top of the file after VALID_TYPES
MAX_TOKENS_BY_DIFFICULTY = {
    "easy":   8000,
    "medium": 8000,
    "hard":   4000   # truncate hard contracts to fit free tier
}

def truncate_contract(code: str, max_chars: int = 6000) -> str:
    if len(code) <= max_chars:
        return code
    # Keep first and last portion — vulnerabilities often at start or end
    half = max_chars // 2
    return code[:half] + "\n\n... [truncated for length] ...\n\n" + code[-half:]

def run_agent(difficulty: str = "easy", runs: int = 5):
    env    = SmartContractAuditorEnv(difficulty=difficulty)
    scores = []

    # Use smaller/faster model for hard to avoid token limits
    model = "llama-3.1-8b-instant" if difficulty == "hard" else "llama-3.3-70b-versatile"

    for i in range(runs):
        obs = env.reset()
        try:
            contract_code = truncate_contract(obs.contract_code)
            user_message  = f"{obs.context}\n\n{contract_code}"

            response = client.chat.completions.create(
                model    = model,
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ]
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            parsed = normalize(json.loads(raw))
            action = Action(**parsed)
            result = env.step(action)
            scores.append(result["reward"])

            print(f"  Run {i+1}: score={result['reward']} | "
                  f"TP={result['info']['true_positives']} | "
                  f"FP={result['info']['false_positives']} | "
                  f"missed={result['info']['missed_bugs']}")

        except Exception as e:
            print(f"  Run {i+1}: ERROR — {e}")
            scores.append(0.0)

    avg = round(sum(scores) / len(scores), 3)
    print(f"  → Average score: {avg}")
    return avg

def normalize(parsed: dict) -> dict:
    for v in parsed.get("vulnerabilities", []):
        if v.get("type") not in VALID_TYPES:
            v["type"] = "other"
        if not v.get("severity"):
            v["severity"] = "medium"
        if not v.get("location"):
            v["location"] = "unknown"
        if not v.get("explanation"):
            v["explanation"] = "no explanation provided"
    return parsed

def run_agent(difficulty: str = "easy", runs: int = 5):
    env    = SmartContractAuditorEnv(difficulty=difficulty)
    scores = []

    for i in range(runs):
        obs = env.reset()
        try:
            user_message = f"{obs.context}\n\n{obs.contract_code}"

            response = client.chat.completions.create(
                model    = "llama-3.3-70b-versatile",
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ]
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            parsed = normalize(json.loads(raw))
            action = Action(**parsed)
            result = env.step(action)
            scores.append(result["reward"])

            print(f"  Run {i+1}: score={result['reward']} | "
                  f"TP={result['info']['true_positives']} | "
                  f"FP={result['info']['false_positives']} | "
                  f"missed={result['info']['missed_bugs']}")

        except Exception as e:
            print(f"  Run {i+1}: ERROR — {e}")
            scores.append(0.0)

    avg = round(sum(scores) / len(scores), 3)
    print(f"  → Average score: {avg}")
    return avg

if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not found. Create a .env file with your key.")
        sys.exit(1)

    print("Starting baseline agent...\n")
    all_scores = {}
    for level in ["easy", "medium", "hard"]:
        print(f"\n=== {level.upper()} ===")
        all_scores[level] = run_agent(level, runs=5)

    print(f"\n{'='*40}")
    print(f"BASELINE RESULTS:")
    for level, score in all_scores.items():
        print(f"  {level:8s}: {score}")