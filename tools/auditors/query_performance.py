"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [audit]
tags: [L9_TEMPLATE, auditors, performance]
owner: platform
status: active
--- /L9_META ---

Query Performance Auditor — N+1 patterns, unbounded queries.
Bug Classes: A) N_PLUS_ONE (HIGH), B) UNBOUNDED_QUERY (MEDIUM), C) STR_COLLECTION (HIGH)
"""

import ast
import re

from tools.auditors.base import (
    AuditorScope,
    AuditResult,
    AuditTier,
    BaseAuditor,
    register_auditor,
)


@register_auditor
class QueryPerformanceAuditor(BaseAuditor):
    @property
    def name(self):
        return "query_performance"

    @property
    def domain(self):
        return "universal"

    @property
    def tier(self):
        return AuditTier.STATIC

    @property
    def scope(self):
        return AuditorScope(
            include=["engine/**/*.py"],
            exclude=["__pycache__", "tests/"],
            rationale="N+1 and unbounded queries cause production perf issues",
        )

    @property
    def contract_file(self):
        return "docs/contracts/CYPHERSAFETY.md"

    def _scan_n_plus_one(self, tree, rel: str, result: AuditResult, counter: list[int]) -> None:
        """Detect DB/ORM calls inside loops (N+1 pattern)."""
        query_methods = {
            "run",
            "execute",
            "execute_query",
            "execute_read",
            "execute_write",
            "search",
            "browse",
            "read",
        }
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.AsyncFor)):
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                if not isinstance(child.func, ast.Attribute):
                    continue
                if child.func.attr in query_methods:
                    counter[0] += 1
                    result.add(
                        severity="HIGH",
                        code=f"QP-{counter[0]:03d}",
                        rule="A",
                        group="query_performance",
                        category="N_PLUS_ONE",
                        message=f".{child.func.attr}() inside loop (N+1)",
                        file=rel,
                        line=child.lineno,
                        fix_hint="Batch queries outside loop or use UNWIND",
                    )

    def _scan_unbounded_queries(self, lines: list[str], rel: str, result: AuditResult, counter: list[int]) -> None:
        """Detect Cypher MATCH statements without a LIMIT clause."""
        for i, line in enumerate(lines, 1):
            if "MATCH" in line and ("session" in line or "cypher" in line.lower()):
                ctx = "\n".join(lines[i - 1 : min(i + 5, len(lines))])
                if "RETURN" in ctx and "LIMIT" not in ctx and "count(" not in ctx.lower():
                    counter[0] += 1
                    result.add(
                        severity="MEDIUM",
                        code=f"QP-{counter[0]:03d}",
                        rule="B",
                        group="query_performance",
                        category="UNBOUNDED_QUERY",
                        message="Cypher MATCH with RETURN but no LIMIT",
                        file=rel,
                        line=i,
                        fix_hint="Add LIMIT $limit or pagination",
                    )

    def _scan_str_collections(self, lines: list[str], rel: str, result: AuditResult, counter: list[int]) -> None:
        """Detect str() called on list/dict literals (returns Python repr, not JSON)."""
        for i, line in enumerate(lines, 1):
            if re.search(r"str\s*\(\s*\[", line) or re.search(r"str\s*\(\s*\{", line):
                counter[0] += 1
                result.add(
                    severity="HIGH",
                    code=f"QP-{counter[0]:03d}",
                    rule="C",
                    group="query_performance",
                    category="STR_COLLECTION",
                    message="str() on collection — Python repr, not valid JSON/Cypher",
                    file=rel,
                    line=i,
                    fix_hint="Use json.dumps() or $param",
                    safe_rewrite="json.dumps(collection)",
                )

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        result = AuditResult(auditor_name=self.name)
        counter = [0]
        for pf in files:
            if pf.suffix != ".py":
                continue
            try:
                with pf.open() as f:
                    src = f.read()
                tree = ast.parse(src)
                lines = src.split("\n")
            except Exception:
                continue
            rel = str(pf.relative_to(repo_root))
            self._scan_n_plus_one(tree, rel, result, counter)
            self._scan_unbounded_queries(lines, rel, result, counter)
            self._scan_str_collections(lines, rel, result, counter)
        return result
