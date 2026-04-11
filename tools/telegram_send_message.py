#!/usr/bin/env python3
"""Send a plain-text Telegram message from CI when credentials are set.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment.
Message body: TELEGRAM_CI_MESSAGE (preferred) or --text.

If token or chat id is missing, exits 0 without sending (workflow can stay green).
If message is empty, exits 0. On Telegram API failure, exits 1.

Body is prefixed with @QuantumAI_IgorBot (see telegram_visibility) unless already present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from telegram_visibility import with_visibility_mention


def _send(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
    except urllib.error.URLError as exc:
        msg = f"Telegram request failed: {exc}"
        raise SystemExit(msg) from exc

    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"Telegram invalid JSON response: {raw[:200]!r}"
        raise SystemExit(msg) from exc

    if not parsed.get("ok"):
        desc = parsed.get("description", parsed)
        msg = f"Telegram API error: {desc}"
        raise SystemExit(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text",
        default="",
        help="Message body (overrides TELEGRAM_CI_MESSAGE if non-empty)",
    )
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("Telegram skip — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID unset.", file=sys.stderr)
        raise SystemExit(0)

    env_msg = os.environ.get("TELEGRAM_CI_MESSAGE", "").strip()
    text = (args.text.strip() or env_msg).strip()
    if not text:
        print("Telegram skip — empty message.", file=sys.stderr)
        raise SystemExit(0)

    text = with_visibility_mention(text)
    _send(token, chat, text)
    print("Telegram message sent.")


if __name__ == "__main__":
    main()
