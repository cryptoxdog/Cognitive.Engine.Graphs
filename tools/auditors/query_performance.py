"""Query Performance Auditor — N+1 patterns, unbounded queries.
Bug Classes: A) N_PLUS_ONE (HIGH), B) UNBOUNDED_QUERY (MEDIUM), C) STR_COLLECTION (HIGH)
"""
import ast, re
from pathlib import Path
from typing import Any
from tools.auditors.base import (
    AuditResult, AuditTier, AuditorScope, BaseAuditor, register_auditor,
)

@register_auditor
class QueryPerformanceAuditor(BaseAuditor):
    @property
    def name(self): return "query_performance"
    @property
    def domain(self): return "universal"
    @property
    def tier(self): return AuditTier.STATIC
    @property
    def scope(self):
        return AuditorScope(include=["engine/**/*.py"], exclude=["__pycache__","tests/"],
            rationale="N+1 and unbounded queries cause production perf issues")
    @property
    def contract_file(self): return "docs/contracts/CYPHERSAFETY.md"

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        result = AuditResult(auditor_name=self.name)
        c = 0
        for pf in files:
            if pf.suffix != ".py": continue
            try:
                with open(pf) as f: src = f.read()
                tree = ast.parse(src); lines = src.split("\n")
            except: continue
            rel = str(pf.relative_to(repo_root))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.For, ast.AsyncFor)): continue
                for child in ast.walk(node):
                    if not isinstance(child, ast.Call): continue
                    if not isinstance(child.func, ast.Attribute): continue
                    if child.func.attr in ("run","execute","execute_query","execute_read",
                                           "execute_write","search","browse","read"):
                        c += 1; result.add(severity="HIGH", code=f"QP-{c:03d}", rule="A",
                            group="query_performance", category="N_PLUS_ONE",
                            message=f".{child.func.attr}() inside loop (N+1)",
                            file=rel, line=child.lineno,
                            fix_hint="Batch queries outside loop or use UNWIND")
            for i, line in enumerate(lines, 1):
                if "MATCH" in line and ("session" in line or "cypher" in line.lower()):
                    ctx = "\n".join(lines[i-1:min(i+5, len(lines))])
                    if "RETURN" in ctx and "LIMIT" not in ctx and "count(" not in ctx.lower():
                        c += 1; result.add(severity="MEDIUM", code=f"QP-{c:03d}", rule="B",
                            group="query_performance", category="UNBOUNDED_QUERY",
                            message="Cypher MATCH with RETURN but no LIMIT",
                            file=rel, line=i, fix_hint="Add LIMIT $limit or pagination")
            for i, line in enumerate(lines, 1):
                if re.search(r'str\s*\(\s*\[', line) or re.search(r'str\s*\(\s*\{', line):
                    c += 1; result.add(severity="HIGH", code=f"QP-{c:03d}", rule="C",
                        group="query_performance", category="STR_COLLECTION",
                        message="str() on collection — Python repr, not valid JSON/Cypher",
                        file=rel, line=i, fix_hint="Use json.dumps() or $param",
                        safe_rewrite="json.dumps(collection)")
        return result
