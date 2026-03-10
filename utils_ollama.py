# utils_ollama.py
# Call Ollama Cloud (or compatible) API for chat completion
# Used by the Shiny app for event interpretation and report analysis

# 0. Setup #################################

import requests
from typing import Optional

# 1. Chat function #################################


def ollama_chat(
    prompt: str,
    api_key: str,
    model: str = "gpt-oss:20b-cloud",
    url: str = "https://ollama.com/api/chat",
) -> Optional[str]:
    """
    Send a single user message to Ollama and return the assistant reply text.
    Returns None on failure or missing key.
    """
    if not api_key or not prompt:
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=300)
        r.raise_for_status()
        result = r.json()
        msg = result.get("message") or {}
        return msg.get("content") or None
    except Exception:
        return None
