# ============================================================================
# tests/unit/test_sync.py
# ============================================================================

"""
Unit tests for sync query generation.
Target Coverage: 70%+
"""

import pytest

from engine.sync.generator import SyncGenerator


@pytest.mark.unit
class TestSyncGenerator:
    """Test sync Cypher generation."""

    def test_unwind_merge_generates_merge(self):
        """UNWINDMERGE strategy generates MERGE statements."""
        generator = SyncGenerator(
            node_label="Supplier", properties=["supplierid", "name", "city"], strategy="UNWINDMERGE"
        )

        cypher = generator.generate()

        assert "UNWIND" in cypher
        assert "MERGE" in cypher
        assert "Supplier" in cypher

    def test_unwind_match_set_generates_match_set(self):
        """UNWINDMATCHSET strategy generates MATCH/SET statements."""
        generator = SyncGenerator(
            node_label="Supplier", properties=["name", "city"], strategy="UNWINDMATCHSET", match_key="supplierid"
        )

        cypher = generator.generate()

        assert "UNWIND" in cypher
        assert "MATCH" in cypher
        assert "SET" in cypher

    def test_taxonomy_linking(self):
        """Taxonomy edges are created during sync."""
        generator = SyncGenerator(
            node_label="Supplier",
            properties=["supplierid", "polymertypes"],
            strategy="UNWINDMERGE",
            taxonomy_edges=[{"edgetype": "SUPPLIES", "targetlabel": "PolymerType", "sourcefield": "polymertypes"}],
        )

        cypher = generator.generate()

        assert "SUPPLIES" in cypher
        assert "PolymerType" in cypher

    def test_child_entity_sync(self):
        """Child entities are synced with parent."""
        generator = SyncGenerator(
            node_label="Supplier",
            properties=["supplierid"],
            strategy="UNWINDMERGE",
            children=[
                {"label": "Certification", "relationship": "HAS_CERTIFICATION", "properties": ["certid", "certname"]}
            ],
        )

        cypher = generator.generate()

        assert "HAS_CERTIFICATION" in cypher
        assert "Certification" in cypher
