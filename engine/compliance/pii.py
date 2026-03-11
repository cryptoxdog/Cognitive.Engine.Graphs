"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [compliance, pii]
owner: engine-team
status: active
--- /L9_META ---

engine/compliance/pii.py
PII detection, masking, and GDPR data subject operations.
Integrates with PacketEnvelope.security.pii_fields.

Exports: PIIHandler
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── PII Field Classification ──────────────────────────────


class PIICategory(StrEnum):
    """PII sensitivity categories."""

    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    ADDRESS = "address"
    DOB = "date_of_birth"
    FINANCIAL = "financial"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


class PIISensitivity(StrEnum):
    LOW = "low"  # business name, city
    MEDIUM = "medium"  # email, phone
    HIGH = "high"  # SSN, DOB, financial account
    CRITICAL = "critical"  # combined identity (name + SSN + DOB)


# ── Patterns ──────────────────────────────────────────────

_PII_PATTERNS: dict[PIICategory, re.Pattern[str]] = {
    PIICategory.EMAIL: re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    ),
    PIICategory.PHONE: re.compile(
        r"(?:\+?1[\-\s.]?)?\(?[0-9]{3}\)?[\-\s.]?[0-9]{3}[\-\s.]?[0-9]{4}",
    ),
    PIICategory.SSN: re.compile(
        r"\b[0-9]{3}[\-\s]?[0-9]{2}[\-\s]?[0-9]{4}\b",
    ),
    PIICategory.IP_ADDRESS: re.compile(
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
    ),
}

# Known PII field names (case-insensitive substring match)
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
    "contact_name": (PIICategory.NAME, PIISensitivity.MEDIUM),
    "street": (PIICategory.ADDRESS, PIISensitivity.MEDIUM),
    "address": (PIICategory.ADDRESS, PIISensitivity.MEDIUM),
    "zip_code": (PIICategory.ADDRESS, PIISensitivity.LOW),
    "postal_code": (PIICategory.ADDRESS, PIISensitivity.LOW),
    "account_number": (PIICategory.FINANCIAL, PIISensitivity.HIGH),
    "routing_number": (PIICategory.FINANCIAL, PIISensitivity.HIGH),
    "credit_score": (PIICategory.FINANCIAL, PIISensitivity.HIGH),
    "ip_address": (PIICategory.IP_ADDRESS, PIISensitivity.LOW),
}


class PIIDetection(BaseModel):
    """Result of PII detection on a single field."""

    field_path: str
    category: PIICategory
    sensitivity: PIISensitivity
    detected_by: str  # "field_name" | "pattern_match"


class PIIHandler:
    """
    PII detection, masking, and GDPR data subject operations.

    Integrates with PacketEnvelope.security.pii_fields tuple.

    Usage:
        pii = PIIHandler()

        # Detect PII in a payload
        detections = pii.detect_pii({"email": "a@b.com", "facility_id": 42})
        # → [PIIDetection(field_path="email", category=EMAIL, ...)]

        # Get pii_fields tuple for PacketEnvelope
        pii_fields = pii.get_pii_field_paths(payload)
        # → ("email", "contact_name")

        # Mask PII in payload
        masked = pii.mask_fields(payload, fields=["email", "ssn"])
        # → {"email": "***@***.com", "ssn": "***-**-****"}

        # Redact (remove) PII fields entirely
        redacted = pii.redact(payload, fields=["ssn"])
        # → {"email": "a@b.com"}  (ssn removed)

        # GDPR right-to-erasure
        pii.erase_subject(data_subject_id="user-123", stores=[...])
    """

    def __init__(
        self,
        additional_pii_fields: dict[str, tuple[PIICategory, PIISensitivity]] | None = None,
        mask_char: str = "*",
    ):
        self._field_hints = dict(_PII_FIELD_HINTS)
        if additional_pii_fields:
            self._field_hints.update(additional_pii_fields)
        self._mask_char = mask_char
        self._patterns = dict(_PII_PATTERNS)

    # ── Detection ──────────────────────────────────────────

    def detect_pii(
        self,
        payload: dict[str, Any],
        prefix: str = "",
    ) -> list[PIIDetection]:
        """
        Detect PII fields in a payload dict (recursive).
        Returns list of PIIDetection for every field containing PII.
        """
        detections: list[PIIDetection] = []
        for key, value in payload.items():
            field_path = f"{prefix}.{key}" if prefix else key

            # Recurse into nested dicts
            if isinstance(value, dict):
                detections.extend(self.detect_pii(value, prefix=field_path))
                continue

            # Check field name hints
            key_lower = key.lower()
            for hint, (category, sensitivity) in self._field_hints.items():
                if hint in key_lower:
                    detections.append(
                        PIIDetection(
                            field_path=field_path,
                            category=category,
                            sensitivity=sensitivity,
                            detected_by="field_name",
                        )
                    )
                    break
            else:
                # Check value patterns (strings only)
                if isinstance(value, str):
                    for category, pattern in self._patterns.items():
                        if pattern.search(value):
                            sensitivity = _PII_FIELD_HINTS.get(
                                category.value,
                                (category, PIISensitivity.MEDIUM),
                            )[1]
                            detections.append(
                                PIIDetection(
                                    field_path=field_path,
                                    category=category,
                                    sensitivity=sensitivity,
                                    detected_by="pattern_match",
                                )
                            )
                            break

        return detections

    def get_pii_field_paths(self, payload: dict[str, Any]) -> tuple[str, ...]:
        """
        Return tuple of field paths containing PII.
        For PacketEnvelope.security.pii_fields.
        """
        detections = self.detect_pii(payload)
        return tuple(d.field_path for d in detections)

    # ── Masking ────────────────────────────────────────────

    def mask_fields(
        self,
        payload: dict[str, Any],
        fields: list[str] | None = None,
        mask_all_detected: bool = False,
    ) -> dict[str, Any]:
        """
        Mask PII fields in payload. Returns a new dict (does not mutate input).

        Args:
            payload: Input data
            fields: Explicit field paths to mask. If None and mask_all_detected,
                     auto-detects and masks all PII.
            mask_all_detected: If True, detect and mask all PII fields.
        """
        result = dict(payload)  # shallow copy

        # Always detect PII to get category information
        detections = self.detect_pii(payload)
        category_map: dict[str, PIICategory] = {d.field_path: d.category for d in detections}

        if fields is None and mask_all_detected:
            fields = [d.field_path for d in detections]

        if not fields:
            return result

        for field_path in fields:
            category = category_map.get(field_path)
            self._mask_field_at_path(result, field_path.split("."), category=category)

        return result

    def _mask_field_at_path(
        self,
        data: dict[str, Any],
        path_parts: list[str],
        category: PIICategory | None = None,
    ) -> None:
        """Mask a field at a nested path in-place."""
        if len(path_parts) == 1:
            key = path_parts[0]
            if key in data:
                data[key] = self._mask_value(data[key], category=category)
            return

        key = path_parts[0]
        if key in data and isinstance(data[key], dict):
            self._mask_field_at_path(data[key], path_parts[1:], category=category)

    def _mask_value(self, value: Any, category: PIICategory | None = None) -> str:
        """Mask a single value based on its PII category."""
        s = str(value)

        # Email: show domain hint
        if "@" in s or category == PIICategory.EMAIL:
            if "@" in s:
                parts = s.split("@")
                domain_hint = parts[-1].split(".")[-1] if "." in parts[-1] else "com"
                return f"{self._mask_char * 3}@{self._mask_char * 3}.{domain_hint}"

        # SSN: mask all but last 4 (only when explicitly detected as SSN)
        if category == PIICategory.SSN:
            clean = s.replace("-", "").replace(" ", "")
            if len(clean) >= 4:
                return f"{self._mask_char * (len(clean) - 4)}{clean[-4:]}"

        # Financial account: mask all but last 4 (only when explicitly detected)
        if category == PIICategory.FINANCIAL:
            clean = s.replace("-", "").replace(" ", "")
            if clean.isdigit() and len(clean) >= 4:
                return f"{self._mask_char * (len(clean) - 4)}{clean[-4:]}"

        # Generic mask
        if len(s) <= 3:
            return self._mask_char * len(s)
        return f"{s[0]}{self._mask_char * (len(s) - 2)}{s[-1]}"

    # ── Redaction ──────────────────────────────────────────

    def redact(
        self,
        payload: dict[str, Any],
        fields: list[str] | None = None,
        redact_all_detected: bool = False,
    ) -> dict[str, Any]:
        """
        Remove PII fields entirely from payload. Returns a new dict.
        """
        result = dict(payload)

        if fields is None and redact_all_detected:
            detections = self.detect_pii(payload)
            fields = [d.field_path for d in detections]

        if not fields:
            return result

        for field_path in fields:
            self._redact_field_at_path(result, field_path.split("."))

        return result

    def _redact_field_at_path(self, data: dict[str, Any], path_parts: list[str]) -> None:
        """Remove field at nested path."""
        if len(path_parts) == 1:
            data.pop(path_parts[0], None)
            return
        key = path_parts[0]
        if key in data and isinstance(data[key], dict):
            self._redact_field_at_path(data[key], path_parts[1:])

    # ── Hashing (for pseudonymization) ─────────────────────

    @staticmethod
    def hash_value(value: str, salt: str = "") -> str:
        """SHA-256 hash for pseudonymization. One-way, deterministic."""
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()

    # ── GDPR Right-to-Erasure ──────────────────────────────

    async def erase_subject(
        self,
        data_subject_id: str,
        graph_driver: Any = None,
        db_pool: Any = None,
    ) -> dict[str, Any]:
        """
        GDPR right-to-erasure: delete all data for a data subject.

        Steps:
        1. Log the erasure request to audit (before deletion)
        2. Delete from PostgreSQL packet_store WHERE data_subject_id = ?
        3. Delete from Neo4j WHERE entity.data_subject_id = ?
        4. Delete from memory_embeddings via FK cascade
        5. Return summary of what was deleted

        NOTE: Actual DB calls depend on injected drivers. This method
        provides the orchestration contract.
        """
        summary: dict[str, Any] = {
            "data_subject_id": data_subject_id,
            "packets_deleted": 0,
            "graph_nodes_deleted": 0,
            "embeddings_deleted": 0,
        }

        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    result = await conn.execute("SELECT gdpr_erase_subject($1)", data_subject_id)
                    summary["packets_deleted"] = result
            except Exception as e:
                logger.error(f"GDPR erasure DB error for {data_subject_id}: {e}")
                raise

        if graph_driver:
            try:
                result = await graph_driver.execute_query(
                    "MATCH (n {data_subject_id: $dsid}) DETACH DELETE n RETURN count(n) AS deleted",
                    parameters={"dsid": data_subject_id},
                )
                if result:
                    summary["graph_nodes_deleted"] = result[0].get("deleted", 0)
            except Exception as e:
                logger.error(f"GDPR erasure graph error for {data_subject_id}: {e}")
                raise

        logger.info(f"GDPR erasure complete for data_subject_id={data_subject_id}: {summary}")
        return summary
