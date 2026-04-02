import json, shutil, os
from pathlib import Path

# Load SmartBugs ground truth
with open("vulnerabilities.json") as f:
    vuln_data = json.load(f)

# Map SmartBugs categories → your VulnerabilityType enum
CATEGORY_MAP = {
    "access_control":       "access_control",
    "reentrancy":           "reentrancy",
    "arithmetic":           "integer_overflow",
    "time_manipulation":    "timestamp_dependence",
    "denial_of_service":    "access_control",
    "front_running":        "access_control",
    "short_addresses":      "access_control",
    "unchecked_low_level_calls": "access_control",
    "other":                "access_control",
}

SEVERITY_MAP = {
    "access_control":    "high",
    "reentrancy":        "critical",
    "arithmetic":        "high",
    "time_manipulation": "medium",
}

def assign_difficulty(vuln_count):
    if vuln_count == 1:
        return "easy"
    elif vuln_count == 2:
        return "medium"
    else:
        return "hard"

os.makedirs("tasks/easy",   exist_ok=True)
os.makedirs("tasks/medium", exist_ok=True)
os.makedirs("tasks/hard",   exist_ok=True)

success, skipped = 0, 0

for contract in vuln_data:
    name     = contract["name"]          # ✅ correct key
    path     = contract["path"]          # e.g. dataset/access_control/xyz.sol
    vulns    = contract["vulnerabilities"]  # list of {lines, category}

    sol_path = Path(path)
    if not sol_path.exists():
        skipped += 1
        continue

    difficulty = assign_difficulty(len(vulns))

    # Copy .sol to tasks folder
    dest_sol = Path(f"tasks/{difficulty}/{name}")
    shutil.copy(sol_path, dest_sol)

    # Build ground truth JSON
    ground_truth = {
        "contract_id": name.replace(".sol", ""),
        "difficulty":  difficulty,
        "vulnerabilities": [
            {
                "type":        CATEGORY_MAP.get(v["category"], "access_control"),
                "location":    f"lines {v['lines']}",
                "severity":    SEVERITY_MAP.get(v["category"], "medium"),
                "explanation": f"{v['category']} vulnerability at lines {v['lines']}"
            }
            for v in vulns
        ]
    }

    gt_path = Path(f"tasks/{difficulty}/{name.replace('.sol', '.json')}")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    success += 1

print(f"✅ Done! {success} contracts parsed, {skipped} skipped (missing .sol files)")