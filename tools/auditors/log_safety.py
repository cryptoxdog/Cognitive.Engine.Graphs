"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [audit]
tags: [L9_TEMPLATE, auditors, logging]
owner: platform
status: active
--- /L9_META ---

Log Safety Auditor — catches sensitive data in log/print statements.
Bug Classes: A) SENSITIVE_LOGGED (HIGH), B) CREDENTIAL_PRINT (HIGH), C) STACK_TRACE_LEAK (MEDIUM)
"""

import re
from pathlib import Path

from tools.auditors.base import (
    AuditorScope,
    AuditResult,
    AuditTier,
    BaseAuditor,
    register_auditor,
)

SENSITIVE = [
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "api_secret",
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "private_key",
    "credit_card",
    "ssn",
    "neo4j_password",
    "pg_password",
    "db_password",
]
LOG_RE = re.compile(r"(?:_?logger|logging)\s*\.\s*(?:debug|info|warning|error|critical|exception)\s*\(", re.I)
PRINT_RE = re.compile(r"\bprint\s*\(")


@register_auditor
class LogSafetyAuditor(BaseAuditor):
    @property
    def name(self):
        return "log_safety"

    @property
    def domain(self):
        return "universal"

    @property
    def tier(self):
        return AuditTier.STATIC

    @property
    def scope(self):
        return AuditorScope(
            include=["engine/**/*.py", "tools/**/*.py"],
            exclude=["__pycache__", "tests/"],
            rationale="Sensitive data in logs is a security breach vector",
        )

    @property
    def contract_file(self):
        return "docs/contracts/ERRORHANDLING.md"

    def _scan_sensitive_logs(
        self, pf: Path, repo_root: Path, lines: list[str], result: AuditResult, counter: list[int]
    ) -> None:
        """Detect sensitive tokens written to log or print statements."""
        rel = str(pf.relative_to(repo_root))
        for i, line in enumerate(lines, 1):
            il, ip = LOG_RE.search(line), PRINT_RE.search(line)
            if not (il or ip):
                continue
            if line.lstrip().startswith("#"):
                continue
            ll = line.lower()
            for tok in SENSITIVE:
                if tok in ll:
                    counter[0] += 1
                    result.add(
                        severity="HIGH",
                        code=f"LS-{counter[0]:03d}",
                        rule="A" if il else "B",
                        group="log_safety",
                        category="SENSITIVE_LOGGED" if il else "CREDENTIAL_PRINT",
                        message=f"'{tok}' in {'log' if il else 'print'} statement",
                        file=rel,
                        line=i,
                        fix_hint="Mask or remove sensitive fields",
                    )
                    break

    def _scan_trace_leaks(
        self, pf: Path, repo_root: Path, lines: list[str], result: AuditResult, counter: list[int]
    ) -> None:
        """Detect stack-trace exception strings returned in responses."""
        rel = str(pf.relative_to(repo_root))
        for i, line in enumerate(lines, 1):
            if re.search(r"str\s*\(\s*(?:exc|exception|err|error|e)\s*\)", line):
                if any(kw in line for kw in ("return", "response", "detail=", "message=")):
                    counter[0] += 1
                    result.add(
                        severity="MEDIUM",
                        code=f"LS-{counter[0]:03d}",
                        rule="C",
                        group="log_safety",
                        category="STACK_TRACE_LEAK",
                        message="str(exception) in response leaks internals",
                        file=rel,
                        line=i,
                        fix_hint="Use generic error message; log exception separately",
                    )

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        result = AuditResult(auditor_name=self.name)
        counter = [0]  # mutable counter shared across helpers
        for pf in files:
            if pf.suffix != ".py":
                continue
            try:
                with open(pf) as f:
                    lines = f.readlines()
            except Exception:
                continue
            self._scan_sensitive_logs(pf, repo_root, lines, result, counter)
            self._scan_trace_leaks(pf, repo_root, lines, result, counter)
        return result
