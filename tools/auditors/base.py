"""L9 BaseAuditor Protocol v2 — tiered execution, allowlists, two-phase scanning."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"


class AuditTier(str, Enum):
    STATIC = "static"
    REGRESSION = "regression"
    RUNTIME = "runtime"
    SCHEMA = "schema"


@dataclass
class Finding:
    severity: str
    code: str
    rule: int | str
    group: str
    message: str
    file: str
    line: int = 0
    fix_hint: Optional[str] = None
    safe_rewrite: Optional[str] = None
    category: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    auditor_name: str = ""
    findings: list[Finding] = field(default_factory=list)

    def add(self, **kwargs) -> None:
        self.findings.append(Finding(**kwargs))

    @property
    def blockers(self) -> int:
        return sum(1 for f in self.findings if f.severity in ("BLOCKER", "CRITICAL"))

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HIGH")

    @property
    def has_blocking(self) -> bool:
        return self.blockers > 0 or self.high_count > 0

    @property
    def clean(self) -> bool:
        return len(self.findings) == 0


@dataclass
class AuditorScope:
    include: list[str]
    exclude: list[str] = field(default_factory=list)
    rationale: str = ""

    def resolve(self, repo_root: Path) -> list[Path]:
        files: list[Path] = []
        for pattern in self.include:
            files.extend(repo_root.glob(pattern))
        if self.exclude:
            files = [f for f in files
                     if not any(ex in str(f) for ex in self.exclude)]
        return sorted(set(files))


@dataclass
class Allowlist:
    """Semantic false-positive suppression."""
    modules: set[str] = field(default_factory=set)
    patterns: set[str] = field(default_factory=set)
    rules: dict[str, set[str]] = field(default_factory=dict)

    def is_module_allowed(self, module: str) -> bool:
        if module in self.modules:
            return True
        return any(module.startswith(p.rstrip("*")) for p in self.patterns)

    def is_suppressed(self, rule_code: str, filepath: str) -> bool:
        if rule_code in self.rules:
            return filepath in self.rules[rule_code]
        return False


class BaseAuditor(ABC):
    """Protocol every auditor must implement.
    Lifecycle: register -> resolve scope -> prepare (index) -> scan (check)"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def domain(self) -> str: ...

    @property
    @abstractmethod
    def tier(self) -> AuditTier: ...

    @property
    @abstractmethod
    def scope(self) -> AuditorScope: ...

    @property
    @abstractmethod
    def contract_file(self) -> str: ...

    @property
    def allowlist(self) -> Allowlist:
        return Allowlist()

    @property
    def dependencies(self) -> list[str]:
        return []

    @property
    def requires(self) -> list[str]:
        return []

    def prepare(self, files: list[Path], repo_root: Path) -> dict[str, Any]:
        return {"files": files, "repo_root": repo_root}

    @abstractmethod
    def scan(self, files: list[Path], repo_root: Path,
             index: dict[str, Any] | None = None,
             dep_indexes: dict[str, dict[str, Any]] | None = None) -> AuditResult: ...


_REGISTRY: dict[str, type[BaseAuditor]] = {}


def register_auditor(cls: type[BaseAuditor]) -> type[BaseAuditor]:
    instance = cls()
    _REGISTRY[instance.name] = cls
    return cls


def get_auditor(name: str) -> BaseAuditor:
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(f"Unknown auditor. Available: {available}")
    return _REGISTRY[name]()


def get_all_auditors() -> list[BaseAuditor]:
    return [cls() for cls in _REGISTRY.values()]


def get_auditors_for_domain(domain: str) -> list[BaseAuditor]:
    return [cls() for cls in _REGISTRY.values() if cls().domain == domain]


def get_auditors_for_tier(tier: AuditTier) -> list[BaseAuditor]:
    return [cls() for cls in _REGISTRY.values() if cls().tier == tier]
