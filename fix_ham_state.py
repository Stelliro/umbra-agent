#!/usr/bin/env python3
"""Fix corrupted HAM state values (like -724% attention width)."""
import json, sys
from pathlib import Path
state_file = Path("data/umbra_ai_or_state.json")
if not state_file.exists():
    print("No state file found"); sys.exit(0)
data = json.loads(state_file.read_text())
fixed = False
for key in ["attention_width", "retrieval_depth", "system_entropy"]:
    if key in data:
        val = data[key]
        if isinstance(val, (int, float)) and (val < 0.0 or val > 1.0):
            print(f"  FIX: {key} = {val} -> 0.5")
            data[key] = 0.5; fixed = True
if fixed:
    state_file.write_text(json.dumps(data, indent=2))
    print("State file fixed!")
else:
    print("State values OK")
