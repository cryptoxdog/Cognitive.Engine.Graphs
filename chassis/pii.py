"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: "*"
layer: [compliance]
tags: [chassis, pii, gdpr, masking, engine-agnostic]
owner: platform-team
status: active
--- /L9_META ---

chassis/pii.py — Engine-Agnostic PII Detection & Masking

Extracted from engine/compliance/pii.py. Zero engine imports.

Every constellation node that touches customer data needs PII handling:
    - ENRICH sees raw CRM fields (email, phone, addresses)
    - GRAPH stores entity properties that may contain PII
    - SCORE/ROUTE/FORECAST pass through PII in payloads

The chassis provides detection + masking. Engine-specific GDPR erasure
logic stays in the engine (it needs driver access).
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel


class PIICategory(str, Enum):
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    ADDRESS = "address"
    DOB = "date_of_birth"
    FINANCIAL = "financial"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


class PIISensitivity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_PII_PATTERNS: dict[PIICategory, re.Pattern] = {
    PIICategory.EMAIL: re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    PIICategory.PHONE: re.compile(r"(?:\+?1[\-\s.]?)?\(?[0-9]{3}\)?[\-\s.]?[0-9]{3}[\-\s.]?[0-9]{4}"),
    PIICategory.SSN: re.compile(r"\b[0-9]{3}[\-\s]?[0-9]{2}[\-\s]?[0-9]{4}\b"),
    PIICategory.IP_ADDRESS: re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
}

_PII_FIELD_HINTS: dict[str, tuple[PIICategory, PIISensitivity]] = {
    "email": (PIICategory.EMAIL, PIISensitivity.MEDIUM),
    "phone": (PIICategory.PHONE, PIISensitivity.MEDIUM),
    "ssn": (PIICategory.SSN, PIISensitivity.HIGH),
    "social_security": (PIICategory.SSN, PIISensitivity.HIGH),
    "date_of_birth": (PIICategory.DOB, PIISensitivity.HIGH),
    "dob": (PIICategory.DOB, PIISensitivity.HIGH),
    "first_name": (PIICategory.NAME, PIISensitivity.MEDIUM),
    "last_name": (PIICategory.NAME, PIISensitivity.MEDIUM),
    "full_name": (PIICategory.NAME, PIISensitivity.MEDIUM),
    "address": (PIICategory.ADDRESS, PIISensitivity.MEDIUM),
    "account_number": (PIICategory.FINANCIAL, PIISensitivity.HIGH),
    "credit_score": (PIICategory.FINANCIAL, PIISensitivity.HIGH),
    "ip_address": (PIICategory.IP_ADDRESS, PIISensitivity.LOW),
}


class PIIDetection(BaseModel):
    field_path: str
    category: PIICategory
    sensitivity: PIISensitivity
    detected_by: str


class PIIHandler:
    """
    Detect, mask, and redact PII in arbitrary payloads.
    Zero engine dependencies — works with any dict[str, Any].
    """

    def __init__(
        self,
        additional_fields: dict[str, tuple[PIICategory, PIISensitivity]] | None = None,
        mask_char: str = "*",
    ):
        self._hints = dict(_PII_FIELD_HINTS)
        if additional_fields:
            self._hints.update(additional_fields)
        self._mask_char = mask_char

    def detect(self, payload: dict[str, Any], prefix: str = "") -> list[PIIDetection]:
        """Recursively detect PII fields in a payload."""
        results: list[PIIDetection] = []
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                results.extend(self.detect(value, prefix=path))
                continue
            key_lower = key.lower()
            for hint, (cat, sens) in self._hints.items():
                if hint in key_lower:
                    results.append(PIIDetection(field_path=path, category=cat, sensitivity=sens, detected_by="field_name"))
                    break
            else:
                if isinstance(value, str):
                    for cat, pattern in _PII_PATTERNS.items():
                        if pattern.search(value):
                            sens = _PII_FIELD_HINTS.get(cat.value, (cat, PIISensitivity.MEDIUM))[1]
                            results.append(PIIDetection(field_path=path, category=cat, sensitivity=sens, detected_by="pattern"))
                            break
        return results

    def get_pii_paths(self, payload: dict[str, Any]) -> tuple[str, ...]:
        """For PacketEnvelope.security.pii_fields."""
        return tuple(d.field_path for d in self.detect(payload))

    def mask(self, payload: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
        """Mask specified (or all detected) PII fields. Returns new dict."""
        result = dict(payload)
        if fields is None:
            fields = [d.field_path for d in self.detect(payload)]
        for path in fields:
            self._set_at_path(result, path.split("."), masked=True)
        return result

    def redact(self, payload: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
        """Remove PII fields entirely. Returns new dict."""
        result = dict(payload)
        if fields is None:
            fields = [d.field_path for d in self.detect(payload)]
        for path in fields:
            self._del_at_path(result, path.split("."))
        return result

    @staticmethod
    def hash_value(value: str, salt: str = "") -> str:
        """SHA-256 pseudonymization."""
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()

    def _set_at_path(self, data: dict, parts: list[str], masked: bool) -> None:
        if len(parts) == 1:
            if parts[0] in data:
                data[parts[0]] = self._mask_char * min(len(str(data[parts[0]])), 12)
        elif parts[0] in data and isinstance(data[parts[0]], dict):
            self._set_at_path(data[parts[0]], parts[1:], masked)

    def _del_at_path(self, data: dict, parts: list[str]) -> None:
        if len(parts) == 1:
            data.pop(parts[0], None)
        elif parts[0] in data and isinstance(data[parts[0]], dict):
            self._del_at_path(data[parts[0]], parts[1:])
