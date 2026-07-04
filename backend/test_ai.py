"""Quick Claude (Anthropic) API connection test for the AI explainer.

After adding ANTHROPIC_API_KEY to backend/.env, run from the backend folder:
    .venv\\Scripts\\Activate.ps1
    pip install anthropic
    python test_ai.py

Costs a fraction of a cent (a ~30-token question + short answer).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of where this is run from.
load_dotenv(Path(__file__).resolve().with_name(".env"))

API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"

if not API_KEY:
    print("ANTHROPIC_API_KEY is not set in backend/.env")
    raise SystemExit(1)

try:
    import anthropic
except ImportError:
    print("Install the library first:  pip install anthropic")
    raise SystemExit(1)

print(f"Asking Claude ({MODEL}) a quick test question...")
client = anthropic.Anthropic(api_key=API_KEY)

try:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=(
            "You are a concise financial educator for Indian retail investors. "
            "Explain simply in 1-2 sentences. This is education, not investment advice."
        ),
        messages=[{"role": "user", "content": "In one sentence, what is portfolio beta?"}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    print("AI OK - model:", resp.model)
    print("Reply:", text)
    print("Tokens used - in:", resp.usage.input_tokens, "out:", resp.usage.output_tokens)
    print("\nYour AI explainer key works.")
except anthropic.AuthenticationError:
    print("AUTH FAILED: the API key is invalid or mistyped.")
except anthropic.PermissionDeniedError:
    print("PERMISSION DENIED: the key lacks access (often means no credits / billing not set up).")
except anthropic.APIStatusError as e:
    msg = getattr(e, "message", str(e))
    print("API ERROR:", e.status_code, msg)
    if "credit" in str(msg).lower() or "billing" in str(msg).lower():
        print("This looks like a billing issue - add prepaid credits in the Anthropic Console.")
