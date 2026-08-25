#!/usr/bin/env python3
"""Safe Groq API connectivity diagnostic (never prints API keys)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from config.settings import get_settings
from src.agent.groq_client import check_groq_connectivity, inspect_groq_config


def main() -> int:
    print("Groq Connectivity Diagnostic")
    print("=" * 40)

    try:
        settings = get_settings()
    except Exception as exc:
        print(f"CONFIG ERROR: {type(exc).__name__}: {exc}")
        print("Ensure .env contains GROQ_API_KEY and GROQ_MODEL.")
        return 1

    config = inspect_groq_config(settings)
    print(f"API key present: {config.api_key_present}")
    print(f"Model:           {config.model}")
    print(f"SDK:             {config.sdk}")
    print()

    print("Test 1: Minimal chat completion (no tools)")
    result = check_groq_connectivity(settings)
    status = "PASS" if result.ok else "FAIL"
    print(f"  {status}: {result.category.value}")
    print(f"  {result.message}")
    if result.http_status:
        print(f"  HTTP status: {result.http_status}")
    if result.response_preview:
        print(f"  Response preview: {result.response_preview!r}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
