from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class OutcomeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    entity_id: str
    action_name: str
    canonical_label: str
    outcome_state: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReinforcementResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    graph_applied: bool
    scoring_adjustment: float
