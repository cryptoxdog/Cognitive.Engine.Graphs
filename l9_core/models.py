from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    actor: str


class PacketLineage(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_id: str
    parent_id: str | None = None
    hop_count: int = 0


class PacketEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    packet_id: str = Field(default_factory=lambda: str(uuid4()))
    packet_type: str
    tenant: TenantContext
    payload: dict[str, Any]
    lineage: PacketLineage
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str = ""

    @field_validator("packet_type")
    @classmethod
    def validate_packet_type(cls, value: str) -> str:
        if value != value.lower() or "-" in value or " " in value:
            raise ValueError("packet_type must be lowercase snake_case")
        return value

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            object.__setattr__(self, "content_hash", self.compute_content_hash())

    def compute_content_hash(self) -> str:
        canonical_json = json.dumps(
            {
                "packet_type": self.packet_type,
                "tenant": self.tenant.model_dump(mode="json"),
                "payload": self.payload,
                "lineage": self.lineage.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return sha256(canonical_json.encode("utf-8")).hexdigest()

    def derive(self, packet_type: str, payload: dict[str, Any]) -> PacketEnvelope:
        return PacketEnvelope(
            packet_type=packet_type,
            tenant=self.tenant,
            payload=payload,
            lineage=PacketLineage(
                root_id=self.lineage.root_id,
                parent_id=self.packet_id,
                hop_count=self.lineage.hop_count + 1,
            ),
        )


def make_root_packet(packet_type: str, tenant_id: str, actor: str, payload: dict[str, Any]) -> PacketEnvelope:
    packet_id = str(uuid4())
    return PacketEnvelope(
        packet_id=packet_id,
        packet_type=packet_type,
        tenant=TenantContext(tenant_id=tenant_id, actor=actor),
        payload=payload,
        lineage=PacketLineage(root_id=packet_id, parent_id=None, hop_count=0),
    )
