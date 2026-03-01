"""
Admin router: Domain management and schema initialization.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from engine.api.app import get_graph_driver
from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory domain registry (for uploaded specs)
_domain_registry: dict[str, DomainSpec] = {}


class DomainInfo(BaseModel):
    """Domain info response."""
    id: str
    name: str
    version: str
    node_count: int
    edge_count: int
    gate_count: int


class SchemaInitResult(BaseModel):
    """Schema initialization result."""
    domain_id: str
    constraints_created: int
    indexes_created: int
    status: str


def get_domain_spec(domain_id: str) -> DomainSpec:
    """Get domain spec from registry or filesystem."""
    if domain_id in _domain_registry:
        return _domain_registry[domain_id]
    
    # Try filesystem
    domains_root = Path("domains")
    spec_path = domains_root / domain_id / "spec.yaml"
    
    if not spec_path.exists():
        # Try flat file naming convention
        flat_path = domains_root / f"{domain_id}_domain_spec.yaml"
        if flat_path.exists():
            spec_path = flat_path
        else:
            raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    
    with open(spec_path) as f:
        raw = yaml.safe_load(f)
    
    return DomainSpec.model_validate(raw)


@router.get("/domains", response_model=list[DomainInfo])
async def list_domains() -> list[DomainInfo]:
    """List all available domains."""
    domains = []
    
    # From registry
    for domain_id, spec in _domain_registry.items():
        domains.append(DomainInfo(
            id=spec.domain.id,
            name=spec.domain.name,
            version=spec.domain.version,
            node_count=len(spec.ontology.nodes) if spec.ontology else 0,
            edge_count=len(spec.ontology.edges) if spec.ontology else 0,
            gate_count=len(spec.gates) if spec.gates else 0,
        ))
    
    # From filesystem
    domains_root = Path("domains")
    if domains_root.exists():
        for path in domains_root.glob("*_domain_spec.yaml"):
            try:
                with open(path) as f:
                    raw = yaml.safe_load(f)
                spec = DomainSpec.model_validate(raw)
                if spec.domain.id not in [d.id for d in domains]:
                    domains.append(DomainInfo(
                        id=spec.domain.id,
                        name=spec.domain.name,
                        version=spec.domain.version,
                        node_count=len(spec.ontology.nodes) if spec.ontology else 0,
                        edge_count=len(spec.ontology.edges) if spec.ontology else 0,
                        gate_count=len(spec.gates) if spec.gates else 0,
                    ))
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")
    
    return domains


@router.post("/domains/upload", response_model=DomainInfo)
async def upload_domain(file: UploadFile = File(...)) -> DomainInfo:
    """
    Upload a domain spec YAML file.
    
    The spec will be validated and registered in memory.
    """
    if not file.filename or not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=400, detail="File must be a YAML file")
    
    content = await file.read()
    
    try:
        raw = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    
    try:
        spec = DomainSpec.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Schema validation failed: {e}")
    
    # Register in memory
    _domain_registry[spec.domain.id] = spec
    logger.info(f"Registered domain '{spec.domain.id}' v{spec.domain.version}")
    
    return DomainInfo(
        id=spec.domain.id,
        name=spec.domain.name,
        version=spec.domain.version,
        node_count=len(spec.ontology.nodes) if spec.ontology else 0,
        edge_count=len(spec.ontology.edges) if spec.ontology else 0,
        gate_count=len(spec.gates) if spec.gates else 0,
    )


@router.post("/domains/{domain_id}/init-schema", response_model=SchemaInitResult)
async def init_schema(domain_id: str) -> SchemaInitResult:
    """
    Initialize Neo4j schema for a domain.
    
    Creates:
    - Uniqueness constraints for node ID properties
    - Indexes for frequently queried properties
    - Database if it doesn't exist (Enterprise only)
    """
    spec = get_domain_spec(domain_id)
    driver = get_graph_driver()
    
    constraints_created = 0
    indexes_created = 0
    
    # Create constraints and indexes for each node type
    for node in spec.ontology.nodes:
        # Find the ID property (first required string property)
        id_prop = next(
            (p.name for p in node.properties if p.required and p.type == "string"),
            None
        )
        
        if id_prop:
            # Create uniqueness constraint
            constraint_name = f"constraint_{node.label}_{id_prop}"
            try:
                await driver.execute_query(
                    f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                    f"FOR (n:{node.label}) REQUIRE n.{id_prop} IS UNIQUE"
                )
                constraints_created += 1
                logger.info(f"Created constraint: {constraint_name}")
            except Exception as e:
                logger.warning(f"Constraint {constraint_name} may already exist: {e}")
        
        # Create indexes for other commonly queried properties
        for prop in node.properties:
            if prop.name != id_prop and prop.type in ("string", "int", "float", "enum"):
                index_name = f"index_{node.label}_{prop.name}"
                try:
                    await driver.execute_query(
                        f"CREATE INDEX {index_name} IF NOT EXISTS "
                        f"FOR (n:{node.label}) ON (n.{prop.name})"
                    )
                    indexes_created += 1
                except Exception as e:
                    logger.debug(f"Index {index_name} may already exist: {e}")
    
    return SchemaInitResult(
        domain_id=domain_id,
        constraints_created=constraints_created,
        indexes_created=indexes_created,
        status="success",
    )


@router.get("/domains/{domain_id}")
async def get_domain(domain_id: str) -> dict[str, Any]:
    """Get full domain specification."""
    spec = get_domain_spec(domain_id)
    return spec.model_dump()


@router.post("/domains/{domain_id}/seed-sample")
async def seed_sample_data(domain_id: str) -> dict[str, Any]:
    """
    Seed sample data for a domain (for testing).
    
    Creates a few sample nodes based on the ontology.
    """
    spec = get_domain_spec(domain_id)
    driver = get_graph_driver()
    
    created = {}
    
    for node in spec.ontology.nodes:
        if node.managedby == "static":
            continue
        
        # Create 3 sample nodes
        label = node.label
        id_prop = next(
            (p.name for p in node.properties if p.required and p.type == "string"),
            "id"
        )
        
        for i in range(1, 4):
            props = {id_prop: f"SAMPLE_{label.upper()}_{i:03d}"}
            
            # Add some sample values for other properties
            for prop in node.properties:
                if prop.name == id_prop:
                    continue
                if prop.type == "string":
                    props[prop.name] = f"Sample {prop.name} {i}"
                elif prop.type == "int":
                    props[prop.name] = 100 * i
                elif prop.type == "float":
                    props[prop.name] = 10.0 * i
                elif prop.type == "bool":
                    props[prop.name] = i % 2 == 0
            
            try:
                await driver.execute_query(
                    f"MERGE (n:{label} {{{id_prop}: $id}}) SET n += $props",
                    parameters={"id": props[id_prop], "props": props}
                )
            except Exception as e:
                logger.warning(f"Failed to create sample {label}: {e}")
        
        created[label] = 3
    
    return {
        "status": "success",
        "domain_id": domain_id,
        "created": created,
    }
