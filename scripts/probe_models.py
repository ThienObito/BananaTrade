"""Probe which 9Router model IDs answer without printing the API key."""
import os
import sys
from pathlib import Path

import openai
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    base_url = os.environ.get("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
    api_key = os.environ.get("NINEROUTER_API_KEY")
    if not api_key:
        sys.exit("NINEROUTER_API_KEY is not set. Add it to .env.")
    target = sys.argv[1] if len(sys.argv) > 1 else "cx/"
    client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0, timeout=60)
    all_ids = sorted(model.id for model in client.models.list())
    candidates = [target] if target in all_ids else [model for model in all_ids if model.startswith(target) and not model.endswith("-review")]
    if not candidates:
        sys.exit(f"No models match '{target}'.")
    print(f"Probing {len(candidates)} model(s) via {base_url}\n")
    print(f"{'requested':<34} {'status':<6} {'reported model':<28} detail")
    working: list[str] = []
    for model in candidates:
        try:
            response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Reply with the word PASS."}], max_tokens=200)
            text = (response.choices[0].message.content or "").strip()
            print(f"{model:<34} {'OK':<6} {response.model:<28} {text[:20] or '(empty content)'}")
            working.append(f"{model} -> {response.model}")
        except openai.APIError as exc:
            print(f"{model:<34} {'FAIL':<6} {'-':<28} {str(exc).replace(chr(10), ' ')[:110]}")
    print("\nWorking (requested -> reported):")
    for line in working or ["(none)"]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
