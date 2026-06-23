import subprocess
import sys

REQUIRED_PACKAGES = [
    "requests",
    "azure-identity",
    "python-dotenv",
    "pyotp",
]

def _bootstrap():
    import importlib
    missing = []
    pkg_map = {"azure-identity": "azure.identity", "python-dotenv": "dotenv"}
    for pkg in REQUIRED_PACKAGES:
        module = pkg_map.get(pkg, pkg.replace("-", "_"))
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *missing])
        print("Done. Continuing...\n")

_bootstrap()

import base64
import binascii
import hashlib
import os
import pyotp
import requests
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Feitian C200 defaults
MANUFACTURER = "Feitian"
MODEL = "C200"
TIME_STEP = 30  # Feitian C200 is often 60s, but check your specific batch (30 or 60)

GRAPH_BASE = "https://graph.microsoft.com/beta"

def get_graph_token():
    cred = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    token = cred.get_token("https://graph.microsoft.com/.default")
    return token.token

def hex_to_base32(hex_seed):
    """
    Converts a Hexadecimal seed (common in Feitian files) to Base32 
    (required by Microsoft Graph API).
    """
    try:
        # 1. Convert Hex string to raw bytes
        binary_data = binascii.unhexlify(hex_seed)
        # 2. Encode bytes to Base32
        base32_bytes = base64.b32encode(binary_data)
        # 3. Decode back to string for JSON payload
        return base32_bytes.decode('utf-8')
    except Exception as e:
        print(f"Error converting seed: {e}")
        return None

def is_base32(s):
    return all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in s.upper())

def upload_token(serial_number, seed):
    access_token = get_graph_token()

    if is_base32(seed):
        base32_secret = seed.upper()
    else:
        base32_secret = hex_to_base32(seed)

    if not base32_secret:
        return

    endpoint = f"{GRAPH_BASE}/directory/authenticationMethodDevices/hardwareOathDevices"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "serialNumber": serial_number,
        "manufacturer": MANUFACTURER,
        "model": MODEL,
        "secretKey": base32_secret,
        "timeIntervalInSeconds": TIME_STEP,
        "hashFunction": "hmacsha256"  # Crucial for SHA-256 tokens
    }

    response = requests.post(endpoint, headers=headers, json=payload)

    if response.status_code == 201:
        print(f"[OK] Token {serial_number} uploaded.")
        return response.json()['id']
    elif response.status_code == 409:
        print(f"[INFO] Token {serial_number} already exists, looking up existing device...")
        return get_device_id_by_serial(serial_number, headers)
    else:
        print(f"[ERROR] {response.status_code}: {response.text}")
        return None

def get_device_id_by_serial(serial_number, headers):
    endpoint = f"{GRAPH_BASE}/directory/authenticationMethodDevices/hardwareOathDevices"
    params = {"$filter": f"serialNumber eq '{serial_number}'"}
    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code == 200:
        devices = response.json().get('value', [])
        if devices:
            device_id = devices[0]['id']
            print(f"[OK] Found existing device: {device_id}")
            return device_id
    print(f"[ERROR] Could not find existing device: {response.text}")
    return None

def generate_totp(seed):
    base32_secret = seed.upper() if is_base32(seed) else hex_to_base32(seed)
    return pyotp.TOTP(base32_secret, interval=TIME_STEP, digest=hashlib.sha256).now()

def assign_token_to_user(user_id, token_device_id, verification_code):
    access_token = get_graph_token()
    endpoint = f"{GRAPH_BASE}/users/{user_id}/authentication/hardwareOathMethods/assignAndActivate"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "device": {
            "id": token_device_id
        },
        "verificationCode": verification_code
    }

    response = requests.post(endpoint, headers=headers, json=payload)
    if response.status_code == 204:
        print(f"[OK] Token assigned to user {user_id}")
        return True
    else:
        print(f"[ERROR] Assignment failed: {response.text}")
        return False


def process_csv(csv_path):
    import csv
    ok = 0
    failed = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} token(s) from {csv_path}\n")

    for row in rows:
        serial = row.get("serial_number", "").strip()
        seed   = row.get("seed", "").strip()
        user   = row.get("user", "").strip()

        if not serial or not seed or not user:
            print(f"[SKIP] Incomplete row: {row}")
            failed += 1
            continue

        if 'e+' in serial.lower() or 'e-' in serial.lower():
            print(f"[SKIP] Serial '{serial}' looks like scientific notation — Excel has mangled this value. Re-save the CSV with the serial column formatted as Text.")
            failed += 1
            continue

        print(f"--- {serial} -> {user}")
        try:
            device_id = upload_token(serial, seed)
            if device_id:
                code = generate_totp(seed)
                if assign_token_to_user(user, device_id, code):
                    ok += 1
                else:
                    failed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            failed += 1

    print(f"\nDone. {ok} succeeded, {failed} failed.")


def interactive_menu():
    print("=" * 40)
    print("  Feitian OTP Token Manager")
    print("=" * 40)
    print("  1. Single token")
    print("  2. Bulk from CSV")
    print("=" * 40)
    choice = input("Select an option (1 or 2): ").strip()

    if choice == "1":
        serial = input("Serial number: ").strip()
        seed   = input("Seed: ").strip()
        user   = input("User (UPN or Object ID): ").strip()
        print()
        device_id = upload_token(serial, seed)
        if device_id:
            code = generate_totp(seed)
            assign_token_to_user(user, device_id, code)
    elif choice == "2":
        csv_path = input(f"CSV file path [tokens.csv]: ").strip() or "tokens.csv"
        if not os.path.exists(csv_path):
            print(f"[ERROR] CSV file not found: {csv_path}")
            sys.exit(1)
        print()
        process_csv(csv_path)
    else:
        print("[ERROR] Invalid choice.")
        sys.exit(1)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if len(args) == 3:
        serial, seed, user = args
        print(f"--- {serial} -> {user}")
        device_id = upload_token(serial, seed)
        if device_id:
            code = generate_totp(seed)
            assign_token_to_user(user, device_id, code)
    elif len(args) == 1:
        if not os.path.exists(args[0]):
            print(f"[ERROR] CSV file not found: {args[0]}")
            sys.exit(1)
        process_csv(args[0])
    elif len(args) == 0:
        interactive_menu()
    else:
        print("Usage:")
        print("  Interactive: manage_tokens.py")
        print("  Single:      manage_tokens.py <serial> <seed> <user>")
        print("  Bulk:        manage_tokens.py tokens.csv")
        sys.exit(1)
