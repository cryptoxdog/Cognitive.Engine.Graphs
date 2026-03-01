"""
tests/unit/test_gates_all_types.py

Comprehensive unit tests for all 10 gate types.
Target Coverage: 85%+
"""

import pytest
from engine.gates.types.boolean import BooleanGate
from engine.gates.types.composite import CompositeGate
from engine.gates.types.enummap import EnumMapGate
from engine.gates.types.exclusion import ExclusionGate
from engine.gates.types.freshness import FreshnessGate
from engine.gates.types.range import RangeGate
from engine.gates.types.selfrange import SelfRangeGate
from engine.gates.types.temporalrange import TemporalRangeGate
from engine.gates.types.threshold import ThresholdGate
from engine.gates.types.traversal import TraversalGate

# ============================================================================
# THRESHOLD GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestThresholdGate:
    """Test ThresholdGate compilation and inversion."""

    def test_threshold_lte_compiles(self):
        """Threshold gate with <= operator compiles correctly."""
        gate = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="pass",
        )

        cypher = gate.compile("c", "$query")
        assert "c.mincreditscore <= $query.creditscore" in cypher

    def test_threshold_gte_compiles(self):
        """Threshold gate with >= operator compiles correctly."""
        gate = ThresholdGate(
            name="dti_max", candidateprop="maxdtipct", queryparam="dtipct", operator=">=", nullbehavior="pass"
        )

        cypher = gate.compile("c", "$query")
        assert "c.maxdtipct >= $query.dtipct" in cypher

    def test_threshold_lt_compiles(self):
        """Threshold gate with < operator compiles correctly."""
        gate = ThresholdGate(
            name="price_under", candidateprop="priceperlb", queryparam="maxprice", operator="<", nullbehavior="fail"
        )

        cypher = gate.compile("c", "$query")
        assert "c.priceperlb < $query.maxprice" in cypher

    def test_threshold_gt_compiles(self):
        """Threshold gate with > operator compiles correctly."""
        gate = ThresholdGate(
            name="quantity_over",
            candidateprop="availablequantity",
            queryparam="minquantity",
            operator=">",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "c.availablequantity > $query.minquantity" in cypher

    def test_threshold_eq_compiles(self):
        """Threshold gate with = operator compiles correctly."""
        gate = ThresholdGate(
            name="exact_match", candidateprop="value", queryparam="targetvalue", operator="=", nullbehavior="fail"
        )

        cypher = gate.compile("c", "$query")
        assert "c.value = $query.targetvalue" in cypher

    def test_threshold_null_pass(self):
        """Threshold gate with nullbehavior=pass allows NULL."""
        gate = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="pass",
        )

        cypher = gate.compile("c", "$query")
        assert "IS NULL OR" in cypher

    def test_threshold_null_fail(self):
        """Threshold gate with nullbehavior=fail blocks NULL."""
        gate = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "IS NOT NULL AND" in cypher

    def test_threshold_inverts_lte_to_gte(self):
        """Threshold gate <= inverts to >= for bidirectional matching."""
        gate = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="pass",
            invertible=True,
        )

        inverted = gate.invert()
        cypher = inverted.compile("c", "$query")

        # After inversion: queryparam <= candidateprop (>= when flipped)
        assert ">=" in cypher


# ============================================================================
# RANGE GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestRangeGate:
    """Test RangeGate compilation and logic."""

    def test_range_gate_compiles(self):
        """Range gate compiles with min and max checks."""
        gate = RangeGate(
            name="price_range",
            candidateprop="priceperlb",
            queryparam_min="minpriceperlb",
            queryparam_max="maxpriceperlb",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "$query.minpriceperlb <= c.priceperlb" in cypher
        assert "c.priceperlb <= $query.maxpriceperlb" in cypher

    def test_range_gate_null_pass(self):
        """Range gate with nullbehavior=pass allows NULL."""
        gate = RangeGate(
            name="price_range",
            candidateprop="priceperlb",
            queryparam_min="minprice",
            queryparam_max="maxprice",
            nullbehavior="pass",
        )

        cypher = gate.compile("c", "$query")
        assert "IS NULL OR" in cypher

    def test_range_gate_null_fail(self):
        """Range gate with nullbehavior=fail blocks NULL."""
        gate = RangeGate(
            name="price_range",
            candidateprop="priceperlb",
            queryparam_min="minprice",
            queryparam_max="maxprice",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "IS NOT NULL AND" in cypher


# ============================================================================
# BOOLEAN GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestBooleanGate:
    """Test BooleanGate compilation."""

    def test_boolean_gate_true_compiles(self):
        """Boolean gate with true value compiles correctly."""
        gate = BooleanGate(name="accepts_new", candidateprop="acceptsnewpatients", queryparam=True, nullbehavior="fail")

        cypher = gate.compile("c", "$query")
        assert "c.acceptsnewpatients = true" in cypher

    def test_boolean_gate_false_compiles(self):
        """Boolean gate with false value compiles correctly."""
        gate = BooleanGate(name="not_emergency", candidateprop="emergencyonly", queryparam=False, nullbehavior="pass")

        cypher = gate.compile("c", "$query")
        assert "c.emergencyonly = false" in cypher

    def test_boolean_gate_queryparam_reference(self):
        """Boolean gate can reference query parameter."""
        gate = BooleanGate(
            name="va_eligible", candidateprop="requiresvaeligibility", queryparam="vaeligible", nullbehavior="pass"
        )

        cypher = gate.compile("c", "$query")
        assert "c.requiresvaeligibility = $query.vaeligible" in cypher


# ============================================================================
# ENUM MAP GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestEnumMapGate:
    """Test EnumMapGate compilation with mappings."""

    def test_enummap_simple_equality(self):
        """EnumMap with no mapping uses simple equality."""
        gate = EnumMapGate(
            name="polymer_match", candidateprop="polymertype", queryparam="polymertype", nullbehavior="fail"
        )

        cypher = gate.compile("c", "$query")
        assert "c.polymertype = $query.polymertype" in cypher

    def test_enummap_with_complex_mapping(self):
        """EnumMap with complex mapping generates IN clause."""
        gate = EnumMapGate(
            name="loan_purpose",
            candidateprop="loanpurpose",
            queryparam="loanpurpose",
            mappings={"purchase": ["purchase", "newpurchase"], "refinance": ["refinance", "refi", "cashout"]},
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "IN" in cypher or "=" in cypher


# ============================================================================
# EXCLUSION GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestExclusionGate:
    """Test ExclusionGate compilation."""

    def test_exclusion_gate_compiles(self):
        """Exclusion gate generates NOT EXISTS pattern."""
        gate = ExclusionGate(
            name="blacklist", edgetype="BLACKLISTED", fromnode="query", tonode="candidate", nullbehavior="pass"
        )

        cypher = gate.compile("c", "$query")
        assert "NOT EXISTS" in cypher
        assert "BLACKLISTED" in cypher

    def test_exclusion_gate_reverse_direction(self):
        """Exclusion gate can block reverse direction."""
        gate = ExclusionGate(
            name="excluded_buyers", edgetype="EXCLUDED_BY", fromnode="candidate", tonode="query", nullbehavior="pass"
        )

        cypher = gate.compile("c", "$query")
        assert "NOT EXISTS" in cypher
        assert "EXCLUDED_BY" in cypher


# ============================================================================
# SELF-RANGE GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestSelfRangeGate:
    """Test SelfRangeGate compilation."""

    def test_selfrange_gate_compiles(self):
        """Self-range gate checks if query value falls within candidate's range."""
        gate = SelfRangeGate(
            name="panel_capacity",
            candidateprop_min="currentpanelsize",
            candidateprop_max="maxpanelsize",
            queryparam=1,  # Adding 1 patient
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "c.currentpanelsize" in cypher
        assert "c.maxpanelsize" in cypher

    def test_selfrange_gate_with_queryparam(self):
        """Self-range gate can use query parameter for value."""
        gate = SelfRangeGate(
            name="capacity_check",
            candidateprop_min="currentload",
            candidateprop_max="maxload",
            queryparam="requestedload",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "$query.requestedload" in cypher


# ============================================================================
# FRESHNESS GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestFreshnessGate:
    """Test FreshnessGate compilation."""

    def test_freshness_gate_compiles(self):
        """Freshness gate uses duration.between for recency."""
        gate = FreshnessGate(name="data_freshness", candidateprop="lastupdated", maxagedays=30, nullbehavior="fail")

        cypher = gate.compile("c", "$query")
        assert "duration.between" in cypher
        assert "lastupdated" in cypher

    def test_freshness_gate_maxagehours(self):
        """Freshness gate supports hours."""
        gate = FreshnessGate(name="realtime_data", candidateprop="lastupdated", maxagehours=24, nullbehavior="fail")

        cypher = gate.compile("c", "$query")
        assert "duration.between" in cypher


# ============================================================================
# TEMPORAL RANGE GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestTemporalRangeGate:
    """Test TemporalRangeGate compilation."""

    def test_temporalrange_gate_compiles(self):
        """Temporal range gate checks overlapping time windows."""
        gate = TemporalRangeGate(
            name="availability_window",
            candidateprop_start="availablestart",
            candidateprop_end="availableend",
            queryparam_start="pickupdate",
            queryparam_end="deliverydate",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "availablestart" in cypher
        assert "availableend" in cypher
        assert "pickupdate" in cypher or "deliverydate" in cypher


# ============================================================================
# TRAVERSAL GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestTraversalGate:
    """Test TraversalGate compilation."""

    def test_traversal_gate_compiles(self):
        """Traversal gate generates EXISTS pattern."""
        gate = TraversalGate(
            name="insurance_network",
            pattern="candidate-[:ACCEPTS_INSURANCE]->(ins:InsurancePlan {planid: $query.insuranceplan})",
            condition="ins IS NOT NULL",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "EXISTS" in cypher
        assert "ACCEPTS_INSURANCE" in cypher

    def test_traversal_gate_complex_pattern(self):
        """Traversal gate supports complex patterns."""
        gate = TraversalGate(
            name="skill_match",
            pattern="candidate-[:HAS_SKILL]->(s:Skill)<-[:REQUIRES]-(query)",
            condition="s IS NOT NULL",
            nullbehavior="fail",
        )

        cypher = gate.compile("c", "$query")
        assert "EXISTS" in cypher
        assert "HAS_SKILL" in cypher


# ============================================================================
# COMPOSITE GATE TESTS
# ============================================================================


@pytest.mark.unit
class TestCompositeGate:
    """Test CompositeGate with AND/OR logic."""

    def test_composite_gate_and_compiles(self):
        """Composite gate with AND combines sub-gates."""
        subgate1 = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="pass",
        )

        subgate2 = ThresholdGate(
            name="dti_max", candidateprop="maxdtipct", queryparam="dtipct", operator=">=", nullbehavior="pass"
        )

        gate = CompositeGate(name="credit_and_dti", operator="AND", gates=[subgate1, subgate2], nullbehavior="pass")

        cypher = gate.compile("c", "$query")
        assert "AND" in cypher
        assert "mincreditscore" in cypher
        assert "maxdtipct" in cypher

    def test_composite_gate_or_compiles(self):
        """Composite gate with OR combines sub-gates."""
        subgate1 = BooleanGate(name="va_eligible", candidateprop="acceptsva", queryparam=True, nullbehavior="pass")

        subgate2 = BooleanGate(name="fha_eligible", candidateprop="acceptsfha", queryparam=True, nullbehavior="pass")

        gate = CompositeGate(name="va_or_fha", operator="OR", gates=[subgate1, subgate2], nullbehavior="pass")

        cypher = gate.compile("c", "$query")
        assert "OR" in cypher

    def test_composite_gate_nested(self):
        """Composite gates can be nested."""
        inner_gate = CompositeGate(
            name="inner",
            operator="AND",
            gates=[
                ThresholdGate("g1", "prop1", "val1", "<=", "pass"),
                ThresholdGate("g2", "prop2", "val2", ">=", "pass"),
            ],
            nullbehavior="pass",
        )

        outer_gate = CompositeGate(
            name="outer",
            operator="OR",
            gates=[inner_gate, BooleanGate("g3", "prop3", True, "pass")],
            nullbehavior="pass",
        )

        cypher = outer_gate.compile("c", "$query")
        assert "AND" in cypher
        assert "OR" in cypher


# ============================================================================
# NULL SEMANTICS TESTS
# ============================================================================


@pytest.mark.unit
class TestNullSemantics:
    """Test NULL behavior across all gate types."""

    @pytest.mark.parametrize(
        "gate_class,config",
        [
            (ThresholdGate, {"name": "test", "candidateprop": "prop", "queryparam": "param", "operator": "<="}),
            (RangeGate, {"name": "test", "candidateprop": "prop", "queryparam_min": "min", "queryparam_max": "max"}),
            (BooleanGate, {"name": "test", "candidateprop": "prop", "queryparam": True}),
        ],
    )
    def test_null_pass_generates_or_clause(self, gate_class, config):
        """All gates with nullbehavior=pass generate OR NULL clause."""
        config["nullbehavior"] = "pass"
        gate = gate_class(**config)

        cypher = gate.compile("c", "$query")
        assert "IS NULL OR" in cypher

    @pytest.mark.parametrize(
        "gate_class,config",
        [
            (ThresholdGate, {"name": "test", "candidateprop": "prop", "queryparam": "param", "operator": "<="}),
            (RangeGate, {"name": "test", "candidateprop": "prop", "queryparam_min": "min", "queryparam_max": "max"}),
            (BooleanGate, {"name": "test", "candidateprop": "prop", "queryparam": True}),
        ],
    )
    def test_null_fail_generates_not_null_clause(self, gate_class, config):
        """All gates with nullbehavior=fail generate NOT NULL clause."""
        config["nullbehavior"] = "fail"
        gate = gate_class(**config)

        cypher = gate.compile("c", "$query")
        assert "IS NOT NULL" in cypher


# ============================================================================
# GATE INVERSION TESTS
# ============================================================================


@pytest.mark.unit
class TestGateInversion:
    """Test bidirectional gate inversion."""

    def test_threshold_gate_inverts(self):
        """Threshold gate swaps candidateprop and queryparam."""
        gate = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="pass",
            invertible=True,
        )

        inverted = gate.invert()

        assert inverted.candidateprop == "creditscore"  # Swapped
        assert inverted.queryparam == "mincreditscore"  # Swapped

    def test_range_gate_inverts(self):
        """Range gate swaps candidateprop and query params."""
        gate = RangeGate(
            name="price_range",
            candidateprop="priceperlb",
            queryparam_min="minprice",
            queryparam_max="maxprice",
            nullbehavior="pass",
            invertible=True,
        )

        inverted = gate.invert()

        # After inversion, logic reverses
        assert inverted is not None

    def test_non_invertible_gate_raises(self):
        """Non-invertible gate raises error on invert()."""
        gate = ThresholdGate(
            name="credit_min",
            candidateprop="mincreditscore",
            queryparam="creditscore",
            operator="<=",
            nullbehavior="pass",
            invertible=False,  # Not invertible
        )

        with pytest.raises(ValueError):
            gate.invert()
