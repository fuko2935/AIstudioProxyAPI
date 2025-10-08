import os
import sys
import requests

API_URL = os.environ.get("CAMOUFOX_API_URL", "http://localhost:2048/v1/chat/completions")

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/send_long_prompt.py <prompt_file>")
        sys.exit(1)

    prompt_path = sys.argv[1]
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    payload = {
        "model": "Qwen3-Max",
        "messages": [
            {"role": "system", "content": "Testing 40960 limit bypass."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    response = requests.post(API_URL, json=payload, timeout=120)
    print("Status:", response.status_code)
    print("Response:", response.text[:200] + ("..." if len(response.text) > 200 else ""))

if __name__ == "__main__":
    main()
