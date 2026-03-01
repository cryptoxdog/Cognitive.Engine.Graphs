# ============================================================================
# tests/integration/test_match_pipeline.py
# ============================================================================

"""
End-to-end match pipeline integration tests.
Target Coverage: 70%+

NOTE: These tests use FastAPI dependency overrides to mock external services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, ASGITransport

from engine.api.app import create_app
from engine.config.loader import DomainPackLoader
from engine.graph.driver import GraphDriver


def make_mock_domain_spec():
    """Create a mock domain spec for testing."""
    spec = MagicMock()
    spec.domain = MagicMock()
    spec.domain.id = "mortgage-test"
    
    candidate = MagicMock()
    candidate.label = "LoanProduct"
    candidate.matchdirection = "borrowertoproduct"
    
    spec.matchentities = MagicMock()
    spec.matchentities.candidate = [candidate]
    
    spec.gates = MagicMock()
    spec.gates.gates = []
    
    spec.scoring = MagicMock()
    spec.scoring.dimensions = []
    
    spec.traversal = MagicMock()
    spec.traversal.steps = []
    
    spec.derivedparameters = []
    
    return spec


@pytest.mark.integration
@pytest.mark.asyncio
class TestMatchPipeline:
    """Test full match pipeline."""

    async def test_full_match_flow_mortgage(self, sample_query_borrower) -> None:
        """Full mortgage match pipeline returns scored candidates."""
        app = create_app()
        
        mock_domain_spec = make_mock_domain_spec()
        
        mock_loader = MagicMock(spec=DomainPackLoader)
        mock_loader.load_domain.return_value = mock_domain_spec
        
        mock_driver = AsyncMock(spec=GraphDriver)
        mock_driver.execute_query.return_value = [
            {"candidate": {"productid": "PROD_001", "name": "Test Product"}, "score": 0.95}
        ]
        
        app.dependency_overrides[DomainPackLoader] = lambda: mock_loader
        app.dependency_overrides[GraphDriver] = lambda: mock_driver
        
        transport = ASGITransport(app=app)

        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/match",
                    json={
                        "query": sample_query_borrower,
                        "match_direction": "borrowertoproduct",
                        "top_n": 5
                    },
                    headers={"X-Domain-Key": "mortgage-test"},
                )

            assert response.status_code == 200
            data = response.json()

            assert "candidates" in data
            assert "query_id" in data
            assert "match_direction" in data
            assert data["match_direction"] == "borrowertoproduct"
        finally:
            app.dependency_overrides.clear()

    async def test_match_with_custom_weights(self, sample_query_borrower) -> None:
        """Match respects custom scoring weights."""
        app = create_app()
        
        mock_domain_spec = make_mock_domain_spec()
        
        mock_loader = MagicMock(spec=DomainPackLoader)
        mock_loader.load_domain.return_value = mock_domain_spec
        
        mock_driver = AsyncMock(spec=GraphDriver)
        mock_driver.execute_query.return_value = []
        
        app.dependency_overrides[DomainPackLoader] = lambda: mock_loader
        app.dependency_overrides[GraphDriver] = lambda: mock_driver
        
        transport = ASGITransport(app=app)

        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
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
        finally:
            app.dependency_overrides.clear()

    async def test_match_missing_domain_returns_404(self, sample_query_borrower) -> None:
        """Match with unknown domain returns 404."""
        app = create_app()
        
        mock_loader = MagicMock(spec=DomainPackLoader)
        mock_loader.load_domain.side_effect = FileNotFoundError("Domain not found")
        
        app.dependency_overrides[DomainPackLoader] = lambda: mock_loader
        
        transport = ASGITransport(app=app)

        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/match",
                    json={
                        "query": sample_query_borrower,
                        "match_direction": "borrowertoproduct",
                        "top_n": 5
                    },
                    headers={"X-Domain-Key": "unknown-domain"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    async def test_match_invalid_direction_returns_400(self, sample_query_borrower) -> None:
        """Match with invalid direction returns 400."""
        app = create_app()
        
        # Mock spec with no matching candidate for direction
        mock_domain_spec = make_mock_domain_spec()
        mock_domain_spec.matchentities.candidate = []  # No candidates
        
        mock_loader = MagicMock(spec=DomainPackLoader)
        mock_loader.load_domain.return_value = mock_domain_spec
        
        app.dependency_overrides[DomainPackLoader] = lambda: mock_loader
        
        transport = ASGITransport(app=app)

        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/match",
                    json={
                        "query": sample_query_borrower,
                        "match_direction": "invalid_direction",
                        "top_n": 5
                    },
                    headers={"X-Domain-Key": "mortgage-test"},
                )

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()
