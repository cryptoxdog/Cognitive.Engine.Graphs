#!/usr/bin/env python3
"""Send a Telegram message for GitHub PR review / bot comment events.

Reads the event from GITHUB_EVENT_PATH (GitHub Actions). Skips unless
TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set and (optional) the actor
passes the bot allowlist.

Env:
  TELEGRAM_BOT_TOKEN — required (repository secret)
  TELEGRAM_CHAT_ID — required (repository variable or env)
  TELEGRAM_REVIEW_NOTIFY_MODE — "bots" (default) or "all"
  TELEGRAM_REVIEW_BOT_ALLOWLIST — optional comma-separated logins; replaces defaults

CodeRabbit (`coderabbitai[bot]`) is always skipped here — Telegram for that bot is
only from `.github/workflows/coderabbit-notify.yml` (Request changes + tailored text).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from telegram_visibility import TELEGRAM_MESSAGE_MAX, VISIBILITY_PREFIX

# GitHub login for CodeRabbit — excluded so coderabbit-notify.yml is the sole Telegram path.
CODERABBIT_BOT_LOGIN = "coderabbitai[bot]"

DEFAULT_BOTS: frozenset[str] = frozenset(
    {
        "github-actions[bot]",
        "copilot-pull-request-reviewer[bot]",
    }
)


def _truncate(text: str, max_len: int) -> str:
    text = text.strip() if text else ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return "..."
    return text[: max_len - 3] + "..."


def _allowlist() -> frozenset[str]:
    raw = os.environ.get("TELEGRAM_REVIEW_BOT_ALLOWLIST", "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return DEFAULT_BOTS


def _telegram_credentials() -> tuple[str, str] | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return None
    return token, chat


def _load_event() -> dict[str, Any]:
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or not os.path.isfile(path):
        msg = "GITHUB_EVENT_PATH missing or not a file"
        raise SystemExit(msg)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _extract(event: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Returns kind, actor, body, pr_url, detail_url."""
    name = os.environ.get("GITHUB_EVENT_NAME", "")

    if name == "pull_request_review_comment":
        c = event.get("comment") or {}
        pr = event.get("pull_request") or {}
        actor = (c.get("user") or {}).get("login", "")
        body = str(c.get("body") or "")
        pr_url = str(pr.get("html_url") or "")
        detail = str(c.get("html_url") or pr_url)
        kind = "inline review comment"
        return kind, actor, body, pr_url, detail

    if name == "issue_comment":
        issue = event.get("issue") or {}
        if not issue.get("pull_request"):
            raise SystemExit(0)  # not a PR — skip quietly
        c = event.get("comment") or {}
        actor = (c.get("user") or {}).get("login", "")
        body = str(c.get("body") or "")
        pr_url = str(issue.get("html_url") or "")
        detail = str(c.get("html_url") or pr_url)
        kind = "PR comment"
        return kind, actor, body, pr_url, detail

    if name == "pull_request_review":
        rev = event.get("review") or {}
        pr = event.get("pull_request") or {}
        actor = (rev.get("user") or {}).get("login", "")
        state = str(rev.get("state") or "")
        body = str(rev.get("body") or "")
        pr_url = str(pr.get("html_url") or "")
        detail = str(rev.get("html_url") or pr_url)
        kind = f"review submitted ({state})"
        return kind, actor, body, pr_url, detail

    msg = f"unsupported event: {name}"
    raise SystemExit(msg)


def _send_telegram(token: str, chat_id: str, text: str) -> None:
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
    mode = os.environ.get("TELEGRAM_REVIEW_NOTIFY_MODE", "bots").strip().lower()
    creds = _telegram_credentials()
    if not creds:
        print("Telegram skipped — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.", file=sys.stderr)
        raise SystemExit(0)

    token, chat_id = creds
    event = _load_event()
    kind, actor, body, pr_url, detail_url = _extract(event)

    if actor == CODERABBIT_BOT_LOGIN:
        print(
            "Skip notify: CodeRabbit — use coderabbit-notify.yml (Request changes).",
            file=sys.stderr,
        )
        raise SystemExit(0)

    if mode != "all":
        if actor not in _allowlist():
            print(f"Skip notify: actor {actor!r} not in allowlist (mode=bots).", file=sys.stderr)
            raise SystemExit(0)

    repo = os.environ.get("GITHUB_REPOSITORY", "repo")
    header = (
        VISIBILITY_PREFIX + f"GitHub review activity — {repo}\n"
        f"Type: {kind}\n"
        f"Author: {actor}\n"
        f"PR: {pr_url or '—'}\n"
        f"Link: {detail_url or pr_url or '—'}\n"
        f"Preview:\n"
    )
    budget = TELEGRAM_MESSAGE_MAX - len(header) - 1
    budget = max(budget, 80)
    text = header + _truncate(body, budget)
    if len(text) > TELEGRAM_MESSAGE_MAX:
        text = _truncate(text, TELEGRAM_MESSAGE_MAX)

    _send_telegram(token, chat_id, text)
    print("Telegram notification sent.")


if __name__ == "__main__":
    main()
