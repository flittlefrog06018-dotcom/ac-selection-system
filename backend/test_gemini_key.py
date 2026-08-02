"""Test gemini-3.6-flash specifically"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "config.env"), override=True)

api_key = os.getenv("GEMINI_API_KEY", "").strip()
print(f"[TEST] API Key prefix: {api_key[:10]}... (len={len(api_key)})")

from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)

test_models = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-2.5-flash']
for model_name in test_models:
    try:
        print(f"\n[TEST] Calling {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=["Reply with exactly: TEST_OK"],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        print(f"  SUCCESS {model_name}: {response.text[:200]}")
        break
    except Exception as e:
        err = str(e)
        if "429" in err:
            print(f"  QUOTA_EXHAUSTED {model_name} - trying next...")
        elif "404" in err:
            print(f"  NOT_FOUND {model_name} - trying next...")
        else:
            print(f"  FAIL {model_name}: {err[:200]}")
