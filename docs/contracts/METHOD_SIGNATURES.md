<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts]
owner: platform
status: active
/L9_META -->

<!-- L9_TEMPLATE: true -->
# L9 Method Signature Contract

## Rule
Every class constructor and public method has a FIXED signature. Agents must not
add, remove, or reorder parameters without updating this contract AND all callers.

## Constructor Signatures

### DomainPackLoader
```python
class DomainPackLoader:
    def __init__(self, domains_dir: Path = Path("domains")) -> None: ...
    def load_domain(self, domain_id: str) -> DomainSpec: ...
    def list_domains(self) -> list[str]: ...
```


### GateCompiler

```python
class GateCompiler:
    def __init__(self, domain_spec: DomainSpec) -> None: ...
    def compile_all_gates(self, match_direction: str) -> str: ...
    def compile_gate(self, gate: GateSpec, match_direction: str) -> str | None: ...
```


### TraversalAssembler

```python
class TraversalAssembler:
    def __init__(self, domain_spec: DomainSpec) -> None: ...
    def assemble_traversal(self, match_direction: str) -> list[str]: ...
```


### ScoringAssembler

```python
class ScoringAssembler:
    def __init__(self, domain_spec: DomainSpec) -> None: ...
    def assemble_scoring_clause(self, match_direction: str, weights: dict[str, float] | None = None) -> str: ...
```


### ParameterResolver

```python
class ParameterResolver:
    def __init__(self, domain_spec: DomainSpec) -> None: ...
    def resolve_parameters(self, query: dict[str, Any]) -> dict[str, Any]: ...
```


### SyncGenerator

```python
class SyncGenerator:
    def __init__(self, domain_spec: DomainSpec) -> None: ...
    def generate_sync_query(self, endpoint: SyncEndpoint, batch: list[dict[str, Any]]) -> str: ...
```


### GraphDriver

```python
class GraphDriver:
    def __init__(self, uri: str, username: str, password: str) -> None: ...
    async def execute_query(self, cypher: str, parameters: dict[str, Any], database: str) -> list[dict[str, Any]]: ...
    async def close(self) -> None: ...
```


### GDSScheduler

```python
class GDSScheduler:
    def __init__(self, graph_driver: GraphDriver, domain_loader: DomainPackLoader) -> None: ...
    def register_jobs(self) -> None: ...
    async def execute_job(self, domain_id: str, job_name: str) -> dict[str, Any]: ...
```


## How to Add a New Parameter

1. Update this contract file FIRST
2. Update the class
3. Update ALL callers (search with `rg "ClassName("`)
4. Update tests
5. Run `make test` to verify no signature mismatches
```
