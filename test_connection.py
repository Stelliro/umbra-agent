import requests
import json
import random
import os
from datetime import datetime

# Generate a random name to avoid "Name Taken" errors during testing
random_suffix = random.randint(1000, 9999)
TEST_NAME = f"UMBRA_TestUnit_{random_suffix}"

print(f"--- DIAGNOSTIC MODE: Attempting to register {TEST_NAME} ---")

try:
    # 1. Check Server Health
    print("1. Pinging Moltbook server...")
    response = requests.get("https://www.moltbook.com/api/v1/posts?limit=1")
    if response.status_code == 200:
        print("   [OK] Server is reachable.")
    else:
        print(f"   [ERROR] Server returned status code: {response.status_code}")
        print("   STOPPING: Server might be down or blocking you.")
        exit()

    # 2. Attempt Registration
    print(f"2. Registering agent '{TEST_NAME}'...")
    payload = {
        "name": TEST_NAME,
        "description": "Diagnostic Test Unit"
    }
    
    reg_response = requests.post("https://www.moltbook.com/api/v1/agents/register", json=payload)
    data = reg_response.json()

    if "agent" in data:
        print("\n   [SUCCESS] Registration worked!")
        print(f"   API Key: {data['agent']['api_key']}")
        print(f"   Claim URL: {data['agent']['claim_url']}")
        print("\n   >>> ACTION REQUIRED: Copy that Claim URL into your browser immediately to verify. <<<")
        
        # Save this valid key to the config so the GUI picks it up
        config_dir = os.path.expanduser("~/.config/moltbook")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "credentials.json"), "w") as f:
            json.dump({
                "api_key": data['agent']['api_key'], 
                "agent_name": TEST_NAME,
                "saved_at": datetime.now().isoformat()
            }, f)
        print(f"   [SAVED] Credentials saved to {config_dir}\\credentials.json")
        print("   You can now run 'python umbra_gui.py' and start the loop.")
        
    else:
        print("\n   [FAILED] Registration error:")
        print(data)

except Exception as e:
    print(f"\n[CRITICAL ERROR] Could not connect: {e}")