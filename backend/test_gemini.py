"""Quick Google Gemini (free tier) connection test for the AI explainer.

After adding GEMINI_API_KEY to backend/.env, run from the backend folder:
    .venv\\Scripts\\Activate.ps1
    pip install google-genai
    python test_gemini.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of where this is run from.
load_dotenv(Path(__file__).resolve().with_name(".env"))

API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

if not API_KEY:
    print("GEMINI_API_KEY is not set in backend/.env")
    raise SystemExit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Install the library first:  pip install google-genai")
    raise SystemExit(1)

print(f"Asking Gemini ({MODEL}) a quick test question...")
client = genai.Client(api_key=API_KEY)

try:
    resp = client.models.generate_content(
        model=MODEL,
        contents="In one sentence, what is portfolio beta?",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a concise financial educator for Indian retail investors. "
                "Explain simply in 1-2 sentences. This is education, not investment advice."
            ),
            max_output_tokens=200,
        ),
    )
    print("AI OK - model:", MODEL)
    print("Reply:", resp.text)
    print("\nYour free Gemini key works.")
except Exception as e:
    print("GEMINI ERROR:", type(e).__name__, str(e))
    print("\nIf the error mentions the model name, set a different GEMINI_MODEL in .env.")
    print("Models your key can use:")
    try:
        for m in client.models.list():
            print("  -", getattr(m, "name", m))
    except Exception as e2:
        print("  (could not list models:", e2, ")")
