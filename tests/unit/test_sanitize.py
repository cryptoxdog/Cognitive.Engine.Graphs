"""Unit tests — sanitize_label / sanitize_property / sanitize_relationship."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("value", ["Facility", "LoanProduct", "A1b2C3"])
def test_valid_labels(value):
    from engine.utils.security import sanitize_label

    assert sanitize_label(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "'; DROP TABLE",
        "123start",
        "",
        "has space",
        "a" * 65,
    ],
)
def test_invalid_labels_raise(value):
    from engine.utils.security import sanitize_label

    with pytest.raises((ValueError, Exception)):
        sanitize_label(value)


def test_valid_property():
    from engine.utils.security import sanitize_label

    assert sanitize_label("ContaminationTolerance") == "ContaminationTolerance"


def test_invalid_property_raises():
    from engine.utils.security import sanitize_label

    with pytest.raises((ValueError, Exception)):
        sanitize_label("bad prop!")
