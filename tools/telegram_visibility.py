# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: enrichment
# layer: [tools]
# tags: [telegram, ci]
# owner: platform
# status: active
# --- /L9_META ---
"""Shared Telegram @mention so receiving bots see messages in restricted chats."""

from __future__ import annotations

VISIBILITY_BOT_MENTION = "@QuantumAI_IgorBot"
VISIBILITY_PREFIX = f"{VISIBILITY_BOT_MENTION}\n\n"

TELEGRAM_MESSAGE_MAX = 4096


def with_visibility_mention(body: str, max_total: int = TELEGRAM_MESSAGE_MAX) -> str:
    """Prefix with bot mention unless already present; trim to Telegram max length."""
    body = body.strip()
    full = body if body.startswith(VISIBILITY_BOT_MENTION) else VISIBILITY_PREFIX + body
    if len(full) <= max_total:
        return full
    if body.startswith(VISIBILITY_BOT_MENTION):
        if max_total <= 3:
            return "..."
        return full[: max_total - 3] + "..."
    keep = max_total - len(VISIBILITY_PREFIX) - 3
    if keep < 1:
        head = VISIBILITY_PREFIX.rstrip()
        return head[:max_total] if len(head) > max_total else head
    return VISIBILITY_PREFIX + body[:keep] + "..."
