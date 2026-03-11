"""Test Quality Auditor — catches weak, broken, and missing tests.
Bug Classes: A) WEAK_TEST (HIGH), B) EMPTY_TEST_FILE (HIGH),
             C) HANDLER_UNTESTED (MEDIUM), D) FIXTURE_BROKEN (HIGH)
"""
import ast, re
from pathlib import Path
from typing import Any
from tools.auditors.base import (
    AuditResult, AuditTier, AuditorScope, BaseAuditor, register_auditor,
)

def _count_assertions(node):
    count = 0
    for n in ast.walk(node):
        if isinstance(n, ast.Assert): count += 1
        elif isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr.startswith("assert"): count += 1
            elif isinstance(n.func, ast.Name) and n.func.id in ("assert_raises","assertRaises"): count += 1
    return count

def _handler_actions(engine_dir):
    actions = set()
    for py in engine_dir.glob("**/handlers*.py"):
        try:
            with open(py) as f: tree = ast.parse(f.read())
        except: continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("handle_"):
                actions.add(n.name)
    return actions

def _tested_handlers(tests_dir):
    tested = set()
    for py in tests_dir.rglob("test_*.py"):
        try:
            with open(py) as f: content = f.read()
        except: continue
        for m in re.finditer(r'handle_(\w+)', content): tested.add(f"handle_{m.group(1)}")
    return tested

@register_auditor
class TestQualityAuditor(BaseAuditor):
    @property
    def name(self): return "test_quality"
    @property
    def domain(self): return "universal"
    @property
    def tier(self): return AuditTier.STATIC
    @property
    def scope(self):
        return AuditorScope(include=["tests/**/*.py"], exclude=["__pycache__","__init__.py"],
            rationale="Test quality — weak tests create false confidence (H-12)")
    @property
    def contract_file(self): return "docs/contracts/TESTPATTERNS.md"

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        result = AuditResult(auditor_name=self.name)
        c = 0
        for tf in files:
            if tf.name == "__init__.py": continue
            if tf.name == "conftest.py":
                c = self._check_conftest(tf, repo_root, result, c); continue
            if not tf.name.startswith("test_"): continue
            try:
                with open(tf) as f: tree = ast.parse(f.read())
            except: continue
            rel = str(tf.relative_to(repo_root))
            tc = 0
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"): continue
                tc += 1
                if _count_assertions(node) == 0:
                    c += 1; result.add(severity="HIGH", code=f"TQ-{c:03d}", rule="A",
                        group="test_quality", category="WEAK_TEST",
                        message=f"Test '{node.name}' has zero assertions",
                        file=rel, line=node.lineno,
                        fix_hint="Add assert/assertEqual/assertTrue")
            if tc == 0:
                c += 1; result.add(severity="HIGH", code=f"TQ-{c:03d}", rule="B",
                    group="test_quality", category="EMPTY_TEST_FILE",
                    message="Test file has zero test functions", file=rel, line=0,
                    fix_hint="Add test_* functions or remove file")
        ed, td = repo_root/"engine", repo_root/"tests"
        if ed.exists() and td.exists():
            for h in sorted(_handler_actions(ed) - _tested_handlers(td)):
                c += 1; result.add(severity="MEDIUM", code=f"TQ-{c:03d}", rule="C",
                    group="test_quality", category="HANDLER_UNTESTED",
                    message=f"Handler '{h}' has no test coverage", file="engine/", line=0,
                    fix_hint=f"Create tests/test_{h.replace('handle_','')}.py")
        return result

    @staticmethod
    def _check_conftest(conftest, repo_root, result, c):
        try:
            with open(conftest) as f: content = f.read()
        except: return c
        rel = str(conftest.relative_to(repo_root))
        pats = [(r'Path\(\s*["\']\.\/','Fixture uses relative path without __file__ anchor (H-12)'),
                (r'Path\(\s*["\']domains["\']','Fixture uses bare domains path')]
        for pat, msg in pats:
            for m in re.finditer(pat, content):
                ln = content[:m.start()].count("\n") + 1
                c += 1; result.add(severity="HIGH", code=f"TQ-{c:03d}", rule="D",
                    group="test_quality", category="FIXTURE_BROKEN",
                    message=msg, file=rel, line=ln,
                    fix_hint='Use Path(__file__).parent.parent / "domains"')
        return c
