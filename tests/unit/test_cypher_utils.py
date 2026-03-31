"""Unit tests — Cypher utility functions."""
from __future__ import annotations

import pytest


def test_sanitize_label_accepts_valid():
    from engine.utils.security import sanitize_label
    assert sanitize_label("Facility") == "Facility"
    assert sanitize_label("PolymerFamily") == "PolymerFamily"


def test_sanitize_label_rejects_spaces():
    from engine.utils.security import sanitize_label
    with pytest.raises((ValueError, Exception)):
        sanitize_label("bad label")


def test_sanitize_label_rejects_empty():
    from engine.utils.security import sanitize_label
    with pytest.raises((ValueError, Exception)):
        sanitize_label("")


def test_sanitize_label_rejects_sql_injection():
    from engine.utils.security import sanitize_label
    with pytest.raises((ValueError, Exception)):
        sanitize_label("'; DROP TABLE")


def test_sanitize_label_rejects_numeric_start():
    from engine.utils.security import sanitize_label
    with pytest.raises((ValueError, Exception)):
        sanitize_label("123Label")


def test_sanitize_label_rejects_too_long():
    from engine.utils.security import sanitize_label
    with pytest.raises((ValueError, Exception)):
        sanitize_label("A" * 200)
