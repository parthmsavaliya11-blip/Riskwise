"""Quick Angel One SmartAPI connection test (READ-ONLY — never places orders).

Use this to confirm your 4 values work, separate from the rest of the app.

How to run (from the backend folder, with the venv active):
    .venv\\Scripts\\Activate.ps1
    pip install smartapi-python pyotp
    python test_angel.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load the .env that sits next to this script (backend/.env), regardless of cwd.
load_dotenv(Path(__file__).resolve().with_name(".env"))

API_KEY = os.getenv("ANGEL_API_KEY", "").strip()
CLIENT = os.getenv("ANGEL_CLIENT_CODE", "").strip()
PIN = os.getenv("ANGEL_PIN", "").strip()          # your Angel One MPIN
TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "").strip()

missing = [
    name
    for name, val in {
        "ANGEL_API_KEY": API_KEY,
        "ANGEL_CLIENT_CODE": CLIENT,
        "ANGEL_PIN": PIN,
        "ANGEL_TOTP_SECRET": TOTP_SECRET,
    }.items()
    if not val
]
if missing:
    print("These values are missing in backend/.env:", ", ".join(missing))
    raise SystemExit(1)

try:
    import pyotp
    from SmartApi import SmartConnect
except ImportError:
    print("Install the libraries first:  pip install smartapi-python pyotp")
    raise SystemExit(1)

print("1) Generating the 6-digit TOTP from your secret...")
otp = pyotp.TOTP(TOTP_SECRET).now()
print("   TOTP code:", otp)

print("2) Logging in to Angel One (read-only)...")
client = SmartConnect(api_key=API_KEY)
session = client.generateSession(CLIENT, PIN, otp)

if not session or not session.get("status"):
    print("   LOGIN FAILED")
    print("   message:", (session or {}).get("message"))
    print("   errorcode:", (session or {}).get("errorcode"))
    print("   Common causes: wrong MPIN, wrong/expired TOTP secret, or API key not active.")
    raise SystemExit(1)

print("   LOGIN OK")

# Confirm the session by reading your profile (read-only).
try:
    refresh = session["data"]["refreshToken"]
    profile = client.getProfile(refresh)
    name = (profile or {}).get("data", {}).get("name", "(unknown)")
    print("3) Profile name:", name)
except Exception as e:
    print("3) Could not read profile (login still worked):", e)

# Try to read holdings (read-only). Method names vary slightly by SDK version.
try:
    holdings = client.holding()
    rows = (holdings or {}).get("data") or []
    print(f"4) Holdings found: {len(rows)}")
    for r in rows[:5]:
        print(
            "   -",
            r.get("tradingsymbol"),
            "qty", r.get("quantity"),
            "avg", r.get("averageprice"),
            "ltp", r.get("ltp"),
        )
except Exception as e:
    print("4) Holdings call not available on this SDK version (login still worked):", e)

print("\nAll good - your keys work. (Read-only test; no orders were placed.)")
