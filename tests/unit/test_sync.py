"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, sync]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for sync query generation.
Target Coverage: 70%+
"""

from unittest.mock import MagicMock

import pytest

from engine.config.schema import DomainSpec, SyncEndpointSpec, SyncStrategy
from engine.sync.generator import SyncGenerator


def make_mock_domain_spec() -> MagicMock:
    """Create a mock DomainSpec."""
    spec = MagicMock(spec=DomainSpec)
    return spec


def make_mock_sync_endpoint(
    path: str = "/sync/test",
    strategy: SyncStrategy = SyncStrategy.UNWINDMERGE,
    target_node: str = "TestNode",
    id_property: str = "id",
    fields_updated: list[str] | None = None,
    taxonomy_edges: list | None = None,
    child_sync: list | None = None,
) -> MagicMock:
    """Create a mock SyncEndpointSpec."""
    spec = MagicMock(spec=SyncEndpointSpec)
    spec.path = path
    spec.batchstrategy = strategy
    spec.targetnode = target_node
    spec.idproperty = id_property
    spec.fieldsupdated = fields_updated
    spec.taxonomyedges = taxonomy_edges or []
    spec.childsync = child_sync or []
    return spec


@pytest.mark.unit
class TestSyncGenerator:
    """Test sync Cypher generation."""

    def test_unwind_merge_generates_merge(self) -> None:
        """UNWINDMERGE strategy generates MERGE statements."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        endpoint = make_mock_sync_endpoint(
            path="/sync/suppliers",
            strategy=SyncStrategy.UNWINDMERGE,
            target_node="Supplier",
            id_property="supplierid",
        )

        cypher = generator.generate_sync_query(endpoint, batch_data=[])

        assert "UNWIND" in cypher
        assert "MERGE" in cypher
        assert "Supplier" in cypher
        assert "supplierid" in cypher

    def test_unwind_match_set_generates_match_set(self) -> None:
        """UNWINDMATCHSET strategy generates MATCH/SET statements."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        endpoint = make_mock_sync_endpoint(
            path="/sync/suppliers",
            strategy=SyncStrategy.UNWINDMATCHSET,
            target_node="Supplier",
            id_property="supplierid",
            fields_updated=["name", "city"],
        )

        cypher = generator.generate_sync_query(endpoint, batch_data=[])

        assert "UNWIND" in cypher
        assert "MATCH" in cypher
        assert "SET" in cypher
        assert "name" in cypher
        assert "city" in cypher

    def test_taxonomy_linking(self) -> None:
        """Taxonomy edges are created during sync."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        tax_edge = MagicMock()
        tax_edge.targetlabel = "PolymerType"
        tax_edge.targetid = "typeid"
        tax_edge.field = "polymertypes"
        tax_edge.edgetype = "SUPPLIES"

        endpoint = make_mock_sync_endpoint(
            path="/sync/suppliers",
            strategy=SyncStrategy.UNWINDMERGE,
            target_node="Supplier",
            id_property="supplierid",
            taxonomy_edges=[tax_edge],
        )

        cypher = generator.generate_sync_query(endpoint, batch_data=[])

        assert "SUPPLIES" in cypher
        assert "PolymerType" in cypher

    def test_child_entity_sync(self) -> None:
        """Child entities are synced with parent."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        child = MagicMock()
        child.targetnode = "Certification"
        child.targetid = "certid"
        child.field = "certifications"
        child.edgetype = "HAS_CERTIFICATION"
        child.edgedirection = "parenttochild"

        endpoint = make_mock_sync_endpoint(
            path="/sync/suppliers",
            strategy=SyncStrategy.UNWINDMERGE,
            target_node="Supplier",
            id_property="supplierid",
            child_sync=[child],
        )

        cypher = generator.generate_sync_query(endpoint, batch_data=[])

        assert "HAS_CERTIFICATION" in cypher
        assert "Certification" in cypher

    def test_unwind_match_set_updates_all_when_no_fields_specified(self) -> None:
        """UNWINDMATCHSET with no fields_updated uses SET n += row."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        endpoint = make_mock_sync_endpoint(
            path="/sync/suppliers",
            strategy=SyncStrategy.UNWINDMATCHSET,
            target_node="Supplier",
            id_property="supplierid",
            fields_updated=None,
        )

        cypher = generator.generate_sync_query(endpoint, batch_data=[])

        assert "SET n += row" in cypher

    def test_missing_target_node_raises(self) -> None:
        """Missing targetnode raises ValueError."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        endpoint = make_mock_sync_endpoint(
            path="/sync/test",
            strategy=SyncStrategy.UNWINDMERGE,
            target_node=None,
            id_property="id",
        )
        endpoint.targetnode = None

        with pytest.raises(ValueError) as exc_info:
            generator.generate_sync_query(endpoint, batch_data=[])

        assert "targetnode" in str(exc_info.value)

    def test_missing_id_property_raises(self) -> None:
        """Missing idproperty raises ValueError."""
        domain_spec = make_mock_domain_spec()
        generator = SyncGenerator(domain_spec)

        endpoint = make_mock_sync_endpoint(
            path="/sync/test",
            strategy=SyncStrategy.UNWINDMERGE,
            target_node="TestNode",
            id_property=None,
        )
        endpoint.idproperty = None

        with pytest.raises(ValueError) as exc_info:
            generator.generate_sync_query(endpoint, batch_data=[])

        assert "idproperty" in str(exc_info.value)
