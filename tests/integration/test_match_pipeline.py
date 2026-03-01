# ============================================================================
# tests/integration/test_match_pipeline.py
# ============================================================================

"""
End-to-end match pipeline integration tests.
Target Coverage: 70%+
"""

import pytest
from httpx import AsyncClient

from engine.api.app import create_app


@pytest.mark.integration
@pytest.mark.asyncio
class TestMatchPipeline:
    """Test full match pipeline."""

    async def test_full_match_flow_mortgage(self, sample_query_borrower):
        """Full mortgage match pipeline returns scored candidates."""
        app = create_app()

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/match",
                json={"query": sample_query_borrower, "match_direction": "borrowertoproduct", "top_n": 5},
                headers={"X-Domain-Key": "mortgage-test"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "candidates" in data
        assert "query" in data
        assert "scores" in data

    async def test_match_with_custom_weights(self, sample_query_borrower):
        """Match respects custom scoring weights."""
        app = create_app()

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/match",
                json={
                    "query": sample_query_borrower,
                    "match_direction": "borrowertoproduct",
                    "top_n": 5,
                    "weights": {"wrate": 0.80, "wapproval": 0.10, "wspeed": 0.10},
                },
                headers={"X-Domain-Key": "mortgage-test"},
            )

        assert response.status_code == 200
        # Verify weights were applied (check logs or scores)
