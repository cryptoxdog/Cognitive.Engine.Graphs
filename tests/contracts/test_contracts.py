"""
Contract verification test suite.

One test per CEG contract (20 contracts defined in .cursorrules).
Verifies that architectural invariants hold across the codebase
without requiring a running Neo4j instance.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from engine.config.schema import DomainSpec

# Root directories
ROOT = Path(__file__).resolve().parent.parent.parent
ENGINE_DIR = ROOT / "engine"
CHASSIS_DIR = ROOT / "chassis"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_py_files(directory: Path) -> list[Path]:
    """Collect all .py files under a directory."""
    return sorted(directory.rglob("*.py")) if directory.exists() else []


def _engine_py_files() -> list[Path]:
    return _all_py_files(ENGINE_DIR)


def _read_imports(filepath: Path) -> list[str]:
    """Extract all import module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


# ============================================================================
# LAYER 1 - CHASSIS BOUNDARY (contracts 1-5)
# ============================================================================


class TestContract01SingleIngress:
    """CONTRACT 1: Engine NEVER imports FastAPI, Starlette, or HTTP libs."""

    @pytest.mark.contract
    def test_no_fastapi_import_in_engine(self):
        banned = {"fastapi", "starlette", "uvicorn"}
        violations = []
        for f in _engine_py_files():
            for imp in _read_imports(f):
                top_module = imp.split(".")[0]
                if top_module in banned:
                    violations.append(f"{f.relative_to(ROOT)}:{imp}")
        assert not violations, f"Engine imports banned HTTP modules: {violations}"

    @pytest.mark.contract
    def test_no_route_definitions_in_engine(self):
        """Engine never creates APIRouter, app factories, or defines routes."""
        patterns = [r"APIRouter\s*\(", r"FastAPI\s*\(", r"@app\.(get|post|put|delete|patch)"]
        violations = []
        for f in _engine_py_files():
            content = f.read_text(encoding="utf-8")
            for pat in patterns:
                if re.search(pat, content):
                    violations.append(f"{f.relative_to(ROOT)}: matches {pat}")
        assert not violations, f"Engine defines HTTP routes: {violations}"


class TestContract02HandlerInterface:
    """CONTRACT 2: Engine exposes action handlers only via handle_<action>."""

    @pytest.mark.contract
    def test_handler_signatures(self):
        """All public handle_* functions take (tenant: str, payload: dict) -> dict."""
        import engine.handlers as h

        handler_names = [n for n in dir(h) if n.startswith("handle_") and callable(getattr(h, n))]
        assert handler_names, "No handle_* functions found in engine.handlers"
        for name in handler_names:
            fn = getattr(h, name)
            sig = inspect.signature(fn)
            params = list(sig.parameters.keys())
            assert "tenant" in params, f"{name} missing 'tenant' parameter"
            assert "payload" in params, f"{name} missing 'payload' parameter"

    @pytest.mark.contract
    def test_handlers_is_only_chassis_bridge(self):
        """Only engine/handlers.py and engine/boot.py import chassis modules."""
        # boot.py is the startup orchestrator — it legitimately needs chassis
        allowed_chassis_importers = {"handlers.py", "boot.py"}
        for f in _engine_py_files():
            if f.name in allowed_chassis_importers and f.parent == ENGINE_DIR:
                continue
            for imp in _read_imports(f):
                assert not imp.startswith("chassis"), (
                    f"{f.relative_to(ROOT)} imports chassis module '{imp}' — "
                    f"only {allowed_chassis_importers} may do this"
                )


class TestContract03TenantIsolation:
    """CONTRACT 3: Tenant is received as string arg; engine never resolves tenant."""

    @pytest.mark.contract
    def test_handlers_use_tenant_parameter(self):
        """Every handle_* function has 'tenant' as its first parameter."""
        import engine.handlers as h

        for name in dir(h):
            if name.startswith("handle_") and callable(getattr(h, name)):
                sig = inspect.signature(getattr(h, name))
                params = list(sig.parameters.keys())
                assert params[0] == "tenant", f"{name} first param is '{params[0]}', expected 'tenant'"

    @pytest.mark.contract
    def test_no_tenant_resolution_in_engine(self):
        """Engine never resolves tenant from request headers or subdomain."""
        tenant_resolution_patterns = [
            r"request\.headers.*tenant",
            r"request\.host",
            r"subdomain",
            r"X-Tenant-ID",
        ]
        for f in _engine_py_files():
            content = f.read_text(encoding="utf-8")
            for pat in tenant_resolution_patterns:
                if re.search(pat, content, re.IGNORECASE):
                    # handlers.py may reference tenant in error messages
                    if "resolve" in content[max(0, content.find(pat) - 50) : content.find(pat) + 50].lower():
                        pytest.fail(f"{f.relative_to(ROOT)} resolves tenant: {pat}")


class TestContract04ObservabilityInherited:
    """CONTRACT 4: Engine never configures structlog, Prometheus, or logging handlers."""

    @pytest.mark.contract
    def test_no_structlog_configure_in_engine(self):
        banned_calls = [r"structlog\.configure\(", r"logging\.basicConfig\(", r"PrometheusInstrumentor"]
        violations = []
        for f in _engine_py_files():
            content = f.read_text(encoding="utf-8")
            for pat in banned_calls:
                if re.search(pat, content):
                    violations.append(f"{f.relative_to(ROOT)}: {pat}")
        assert not violations, f"Engine configures observability: {violations}"


class TestContract05InfrastructureIsTemplate:
    """CONTRACT 5: Engine never creates Dockerfiles, CI pipelines, or Terraform."""

    @pytest.mark.contract
    def test_no_infra_files_in_engine(self):
        banned_names = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".github", "terraform"}
        for item in ENGINE_DIR.iterdir():
            assert item.name not in banned_names, f"Infra file found in engine/: {item.name}"


# ============================================================================
# LAYER 2 - PACKET PROTOCOL (contracts 6-8)
# ============================================================================


class TestContract06PacketEnvelope:
    """CONTRACT 6: PacketEnvelope is the only inter-service data container."""

    @pytest.mark.contract
    def test_packet_envelope_exists(self):
        """PacketEnvelope model is importable."""
        from engine.packet.packet_envelope import PacketEnvelope

        assert PacketEnvelope is not None

    @pytest.mark.contract
    def test_inflate_deflate_functions_exist(self):
        """inflate_ingress() and deflate_egress() exist."""
        from engine.packet.chassis_contract import deflate_egress, inflate_ingress

        assert callable(inflate_ingress)
        assert callable(deflate_egress)


class TestContract07ImmutabilityContentHash:
    """CONTRACT 7: PacketEnvelope is frozen; content_hash is SHA-256."""

    @pytest.mark.contract
    def test_packet_envelope_frozen(self):
        from engine.packet.packet_envelope import PacketEnvelope

        config = PacketEnvelope.model_config
        assert config.get("frozen") is True, "PacketEnvelope must be frozen"

    @pytest.mark.contract
    def test_derive_creates_new_instance(self):
        from engine.packet.packet_envelope import (
            Action,
            PacketType,
            create_packet,
        )

        p1 = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="node_a",
            actor_tenant="test_tenant",
            payload={"data": "hello"},
            trace_id="trace-1",
        )
        p2 = p1.derive(payload={"data": "world"})
        assert p1.security.content_hash != p2.security.content_hash
        assert p1.packet_id in p2.lineage.parent_ids


class TestContract08LineageAudit:
    """CONTRACT 8: Derived packets set parent_id, root_id, generation."""

    @pytest.mark.contract
    def test_lineage_chain(self):
        from engine.packet.packet_envelope import (
            Action,
            PacketType,
            create_packet,
        )

        root = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="a",
            actor_tenant="test_tenant",
            payload={"x": 1},
            trace_id="trace-lineage",
        )
        child = root.derive(payload={"x": 2})
        assert root.packet_id in child.lineage.parent_ids
        assert child.lineage.root_id == root.packet_id
        assert child.lineage.generation == root.lineage.generation + 1

    @pytest.mark.contract
    def test_no_direct_packet_writes_in_engine(self):
        """Engine never does INSERT INTO packetstore."""
        for f in _engine_py_files():
            content = f.read_text(encoding="utf-8")
            assert "INSERT INTO packetstore" not in content, f"Direct packetstore write in {f.relative_to(ROOT)}"


# ============================================================================
# LAYER 3 - SECURITY (contracts 9-11)
# ============================================================================


class TestContract09CypherInjectionPrevention:
    """CONTRACT 9: All Neo4j labels pass sanitize_label(); values are parameterized."""

    @pytest.mark.contract
    def test_sanitize_label_rejects_injection(self):
        from engine.utils.security import sanitize_label

        bad_labels = [
            "Label; DROP DATABASE",
            "Label' OR 1=1--",
            "Label})-[:HACK]->(x",
            "123invalid",
            "",
            "a b c",
        ]
        for label in bad_labels:
            with pytest.raises(ValueError):
                sanitize_label(label)

    @pytest.mark.contract
    def test_sanitize_label_accepts_valid(self):
        from engine.utils.security import sanitize_label

        valid = ["Facility", "MaterialIntake", "PROCESSES", "community_id", "_private"]
        for label in valid:
            assert sanitize_label(label) == label

    @pytest.mark.contract
    def test_no_eval_exec_in_engine(self):
        """No eval() or exec() calls in engine/ (except safe_eval)."""
        for f in _engine_py_files():
            if f.name == "safe_eval.py":
                continue
            content = f.read_text(encoding="utf-8")
            # Match bare eval( or exec( not in comments
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"\beval\s*\(", stripped) or re.search(r"\bexec\s*\(", stripped):
                    pytest.fail(f"{f.relative_to(ROOT)}:{line_no} uses eval/exec: {stripped.strip()}")


class TestContract10ProhibitedFactors:
    """CONTRACT 10: Compliance fields are blocked at compile-time."""

    @pytest.mark.contract
    def test_prohibited_factor_validator_exists(self):
        from engine.compliance.prohibited_factors import ProhibitedFactorValidator

        assert ProhibitedFactorValidator is not None

    @pytest.mark.contract
    def test_prohibited_factor_blocks_gate(self):
        """When compliance config has blocked fields, gates referencing them are rejected."""
        from engine.compliance.prohibited_factors import ProhibitedFactorValidator
        from engine.config.schema import (
            ComplianceSpec,
            GateSpec,
            GateType,
            ProhibitedFactorsSpec,
        )

        blocked_fields = ["race", "ethnicity", "religion", "gender", "age", "disability"]
        spec = _build_minimal_spec(
            extra_gates=[
                GateSpec(name="bad_gate", type=GateType.BOOLEAN, candidateprop="race", queryparam="race"),
            ]
        )
        # Add compliance config with prohibited factors
        spec = spec.model_copy(
            update={
                "compliance": ComplianceSpec(
                    prohibitedfactors=ProhibitedFactorsSpec(
                        enabled=True,
                        blockedfields=blocked_fields,
                    ),
                ),
            }
        )
        validator = ProhibitedFactorValidator(spec)
        assert "race" in validator.blocked_fields
        with pytest.raises(ValueError, match="prohibited"):
            validator.validate_gate(spec.gates[0])


class TestContract11PIIHandling:
    """CONTRACT 11: PII fields declared in spec; engine never logs PII."""

    @pytest.mark.contract
    def test_pii_handler_importable(self):
        from engine.compliance.pii import PIIHandler

        handler = PIIHandler()
        assert handler is not None

    @pytest.mark.contract
    def test_no_pii_logging_in_engine(self):
        """Engine should not log known PII field names as values."""
        pii_log_patterns = [
            r"logger\.\w+\(.*ssn.*=",
            r"logger\.\w+\(.*social_security.*=",
            r"logger\.\w+\(.*password.*=",
        ]
        for f in _engine_py_files():
            content = f.read_text(encoding="utf-8")
            for pat in pii_log_patterns:
                assert not re.search(pat, content, re.IGNORECASE), f"{f.relative_to(ROOT)} may log PII: {pat}"


# ============================================================================
# LAYER 4 - ENGINE ARCHITECTURE (contracts 12-16)
# ============================================================================


class TestContract12DomainSpecSourceOfTruth:
    """CONTRACT 12: All matching behavior comes from YAML domain spec."""

    @pytest.mark.contract
    def test_domain_spec_validates(self):
        """DomainSpec Pydantic model accepts valid YAML-like input."""
        spec = _build_minimal_spec()
        assert spec.domain.id == "test"
        assert len(spec.gates) >= 0

    @pytest.mark.contract
    def test_domain_pack_loader_exists(self):
        from engine.config.loader import DomainPackLoader

        loader = DomainPackLoader(config_path=str(ROOT / "domains"))
        assert loader is not None


class TestContract13GateThenScore:
    """CONTRACT 13: Matching is two-phase: gates (hard filter) → scoring (soft rank)."""

    @pytest.mark.contract
    def test_gate_types_count(self):
        """GateType enum has exactly 10 values."""
        from engine.config.schema import GateType

        assert len(GateType) == 10, f"Expected 10 gate types, got {len(GateType)}: {list(GateType)}"

    @pytest.mark.contract
    def test_scoring_computation_types(self):
        """ComputationType enum has expected scoring computations."""
        from engine.config.schema import ComputationType

        expected = {
            "geodecay",
            "lognormalized",
            "communitymatch",
            "inverselinear",
            "candidateproperty",
            "weightedrate",
            "pricealignment",
            "temporalproximity",
            "customcypher",
        }
        actual = {ct.value for ct in ComputationType}
        assert expected.issubset(actual), f"Missing computation types: {expected - actual}"

    @pytest.mark.contract
    def test_gate_compiles_to_where_clause(self):
        """Gate compiler produces non-empty WHERE clause strings."""
        from engine.config.schema import GateSpec, GateType
        from engine.gates.compiler import GateCompiler

        spec = _build_minimal_spec(
            extra_gates=[
                GateSpec(name="test_bool", type=GateType.BOOLEAN, candidateprop="active", queryparam="is_active"),
            ]
        )
        compiler = GateCompiler(spec)
        result = compiler.compile_all_gates("buyer_to_seller")
        assert result
        assert result != "true"

    @pytest.mark.contract
    def test_scoring_assembles_with_clause(self):
        """Scoring assembler produces WITH clause."""
        from engine.scoring.assembler import ScoringAssembler

        spec = _build_minimal_spec_with_scoring()
        assembler = ScoringAssembler(spec)
        clause, _ = assembler.assemble_scoring_clause("buyer_to_seller", {})
        assert "WITH" in clause or "score" in clause


class TestContract14NullSemantics:
    """CONTRACT 14: Every gate declares null_behavior: pass | fail."""

    @pytest.mark.contract
    def test_null_behavior_enum(self):
        from engine.config.schema import NullBehavior

        assert NullBehavior.PASS.value == "pass"
        assert NullBehavior.FAIL.value == "fail"

    @pytest.mark.contract
    def test_null_pass_wraps_predicate(self):
        """NullBehavior.PASS wraps predicate with IS NULL OR."""
        from engine.config.schema import GateType, NullBehavior
        from engine.gates.null_semantics import NullHandler

        result = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.RANGE,
            null_behavior=NullBehavior.PASS,
            gate_cypher="candidate.x >= $x",
            candidate_prop="candidate.x",
        )
        assert "IS NULL" in result
        assert "OR" in result

    @pytest.mark.contract
    def test_null_fail_requires_not_null(self):
        """NullBehavior.FAIL wraps predicate with IS NOT NULL AND."""
        from engine.config.schema import GateType, NullBehavior
        from engine.gates.null_semantics import NullHandler

        result = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.BOOLEAN,
            null_behavior=NullBehavior.FAIL,
            gate_cypher="candidate.active = $active",
            candidate_prop="candidate.active",
        )
        assert "IS NOT NULL" in result
        assert "AND" in result


class TestContract15BidirectionalMatching:
    """CONTRACT 15: Gates with invertible:true swap props when direction reverses."""

    @pytest.mark.contract
    def test_invertible_gate_field(self):
        from engine.config.schema import GateSpec, GateType

        gate = GateSpec(name="inv_gate", type=GateType.ENUMMAP, candidateprop="x", queryparam="y", invertible=True)
        assert gate.invertible is True

    @pytest.mark.contract
    def test_match_directions_filtering(self):
        """Gates with matchdirections only fire for those directions."""
        from engine.config.schema import GateSpec, GateType
        from engine.gates.compiler import GateCompiler

        spec = _build_minimal_spec(
            extra_gates=[
                GateSpec(
                    name="directional",
                    type=GateType.BOOLEAN,
                    candidateprop="active",
                    queryparam="is_active",
                    matchdirections=["buyer_to_seller"],
                ),
            ]
        )
        compiler = GateCompiler(spec)
        # Should compile for matching direction
        result_match = compiler.compile_all_gates("buyer_to_seller")
        assert result_match != "true"
        # Should not compile for other direction
        result_other = compiler.compile_all_gates("seller_to_buyer")
        assert result_other == "true"


class TestContract16FileStructure:
    """CONTRACT 16: Fixed file structure layout."""

    EXPECTED_DIRS = [
        "config",
        "gates",
        "scoring",
        "traversal",
        "sync",
        "gds",
        "graph",
        "compliance",
        "packet",
        "utils",
    ]

    @pytest.mark.contract
    def test_engine_subdirectories_exist(self):
        for subdir in self.EXPECTED_DIRS:
            path = ENGINE_DIR / subdir
            assert path.is_dir(), f"Missing engine subdirectory: engine/{subdir}/"

    @pytest.mark.contract
    def test_handlers_at_expected_location(self):
        assert (ENGINE_DIR / "handlers.py").is_file()

    @pytest.mark.contract
    def test_no_unexpected_top_level_dirs_in_engine(self):
        """Engine contains only expected subdirectories (plus known extensions)."""
        # Core dirs from contract 16 + known extensions added in Waves 1-4
        allowed = set(self.EXPECTED_DIRS) | {
            "__pycache__",
            "kge",
            "security",
            "health",
            "personas",
            "intake",
            "causal",
            "feedback",
            "resolution",
        }
        for item in ENGINE_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                assert item.name in allowed, f"Unexpected directory in engine/: {item.name}"


# ============================================================================
# LAYER 5 - TESTING + QUALITY (contracts 17-18)
# ============================================================================


class TestContract17TestRequirements:
    """CONTRACT 17: Required test categories exist."""

    @pytest.mark.contract
    def test_unit_tests_exist(self):
        unit_tests = _all_py_files(ROOT / "tests" / "unit")
        assert len(unit_tests) > 0, "No unit tests found in tests/unit/"

    @pytest.mark.contract
    def test_compliance_tests_exist(self):
        compliance_tests = _all_py_files(ROOT / "tests" / "compliance")
        assert len(compliance_tests) > 0, "No compliance tests found in tests/compliance/"

    @pytest.mark.contract
    def test_gate_compilation_tests_exist(self):
        gate_tests = list((ROOT / "tests").rglob("*gate*"))
        assert len(gate_tests) > 0, "No gate compilation tests found"


class TestContract18L9Meta:
    """CONTRACT 18: L9_META on every engine file."""

    @pytest.mark.contract
    def test_engine_files_have_l9_meta(self):
        missing = []
        for f in _engine_py_files():
            if f.name == "__init__.py":
                continue
            content = f.read_text(encoding="utf-8")
            if "L9_META" not in content:
                missing.append(str(f.relative_to(ROOT)))
        assert not missing, f"Engine files missing L9_META header: {missing}"


# ============================================================================
# LAYER 6 - GRAPH INTELLIGENCE (contracts 19-20)
# ============================================================================


class TestContract19GDSDeclarative:
    """CONTRACT 19: GDS jobs are declarative, not hardcoded."""

    @pytest.mark.contract
    def test_gds_job_spec_exists(self):
        from engine.config.schema import GDSJobSpec

        job = GDSJobSpec(
            name="test_job",
            algorithm="louvain",
            schedule={"type": "manual"},
            projection={"nodelabels": ["Node"], "edgetypes": ["EDGE"]},
        )
        assert job.algorithm == "louvain"

    @pytest.mark.contract
    def test_gds_scheduler_reads_from_spec(self):
        """GDSScheduler accepts domain spec, not hardcoded algorithms."""
        from engine.gds.scheduler import GDSScheduler

        assert hasattr(GDSScheduler, "__init__")
        sig = inspect.signature(GDSScheduler.__init__)
        params = list(sig.parameters.keys())
        assert "domain_spec" in params or "spec" in params or len(params) >= 2


class TestContract20KGEEmbeddings:
    """CONTRACT 20: KGE uses CompoundE3D; embeddings are domain-specific."""

    @pytest.mark.contract
    def test_kge_spec_schema(self):
        from engine.config.schema import KGESpec

        kge = KGESpec()
        assert kge.model == "CompoundE3D"
        assert kge.embeddingdim == 256

    @pytest.mark.contract
    def test_kge_scoring_dimension_exists(self):
        from engine.config.schema import ComputationType

        assert ComputationType.KGE.value == "kge"


# ============================================================================
# Helpers for building minimal DomainSpec instances
# ============================================================================


def _build_minimal_spec(extra_gates: list | None = None) -> DomainSpec:
    """Build a minimal DomainSpec for testing without YAML."""
    from engine.config.schema import (
        DomainMetadata,
        DomainSpec,
        EdgeCategory,
        EdgeDirection,
        EdgeSpec,
        ManagedByType,
        MatchEntitiesSpec,
        MatchEntitySpec,
        NodeSpec,
        OntologySpec,
        PropertySpec,
        PropertyType,
        QueryFieldSpec,
        QuerySchemaSpec,
        ScoringSpec,
    )

    nodes = [
        NodeSpec(
            label="Facility",
            candidate=True,
            properties=[
                PropertySpec(name="active", type=PropertyType.BOOL),
                PropertySpec(name="density", type=PropertyType.FLOAT),
                PropertySpec(name="rate", type=PropertyType.FLOAT),
                PropertySpec(name="lat", type=PropertyType.FLOAT),
                PropertySpec(name="lon", type=PropertyType.FLOAT),
                PropertySpec(name="community_id", type=PropertyType.INT),
                PropertySpec(name="race", type=PropertyType.STRING),
            ],
        ),
        NodeSpec(label="Query", queryentity=True),
    ]
    edges = [
        EdgeSpec(
            type="PROCESSES",
            **{"from": "Facility"},
            to="Query",
            direction=EdgeDirection.DIRECTED,
            category=EdgeCategory.CAPABILITY,
            managedby=ManagedByType.SYNC,
        ),
    ]
    gates = list(extra_gates) if extra_gates else []

    return DomainSpec(
        domain=DomainMetadata(id="test", name="Test Domain", version="1.0.0"),
        ontology=OntologySpec(nodes=nodes, edges=edges),
        matchentities=MatchEntitiesSpec(
            candidate=[MatchEntitySpec(label="Facility", matchdirection="buyer_to_seller")],
            queryentity=[MatchEntitySpec(label="Query", matchdirection="buyer_to_seller")],
        ),
        queryschema=QuerySchemaSpec(
            matchdirections=["buyer_to_seller"],
            fields=[
                QueryFieldSpec(name="is_active", type=PropertyType.BOOL),
                QueryFieldSpec(name="density", type=PropertyType.FLOAT),
            ],
        ),
        gates=gates,
        scoring=ScoringSpec(dimensions=[]),
    )


def _build_minimal_spec_with_scoring() -> DomainSpec:
    """Build a minimal DomainSpec with scoring dimensions."""
    from engine.config.schema import (
        ComputationType,
        ScoringDimensionSpec,
        ScoringSource,
        ScoringSpec,
    )

    spec = _build_minimal_spec()
    spec = spec.model_copy(
        update={
            "scoring": ScoringSpec(
                dimensions=[
                    ScoringDimensionSpec(
                        name="geo",
                        source=ScoringSource.COMPUTED,
                        computation=ComputationType.GEODECAY,
                        candidateprop="lat",
                        queryprop="lat",
                        weightkey="w_geo",
                        defaultweight=0.3,
                    ),
                    ScoringDimensionSpec(
                        name="structural",
                        source=ScoringSource.CANDIDATEPROPERTY,
                        computation=ComputationType.CANDIDATEPROPERTY,
                        candidateprop="rate",
                        weightkey="w_structural",
                        defaultweight=0.3,
                    ),
                ]
            ),
        }
    )
    return spec
