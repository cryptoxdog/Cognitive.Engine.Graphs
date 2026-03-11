"""API Regression Auditor — detects breaking changes vs main branch.
Prevents: Rule 7 (constructor signature drift), Rule 8 (payload contract drift)
Bug Classes: A) CLASS_REMOVED (CRITICAL), B) METHOD_REMOVED (CRITICAL),
             C) SIGNATURE_CHANGED (HIGH), D) RETURN_TYPE_CHANGED (HIGH)
"""
import ast, subprocess
from pathlib import Path
from typing import Any, Optional
from tools.auditors.base import (
    AuditResult, AuditTier, AuditorScope, BaseAuditor, register_auditor,
)

def _run_git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

def _extract_public_api(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    api = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
            continue
        methods = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name.startswith("_") and item.name != "__init__":
                    continue
                args = [a.arg for a in item.args.args]
                ret = ast.unparse(item.returns) if item.returns else None
                methods[item.name] = {"args": args, "returns": ret}
        api[node.name] = {"methods": methods, "line": node.lineno}
    return api

@register_auditor
class APIRegressionAuditor(BaseAuditor):
    @property
    def name(self): return "api_regression"
    @property
    def domain(self): return "universal"
    @property
    def tier(self): return AuditTier.REGRESSION
    @property
    def scope(self):
        return AuditorScope(include=["engine/**/*.py"], exclude=["__pycache__", "tests/"],
            rationale="Public engine API — breaking changes crash downstream callers")
    @property
    def contract_file(self): return "docs/contracts/METHODSIGNATURES.md"
    @property
    def requires(self): return ["git"]

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        result = AuditResult(auditor_name=self.name)
        c = 0
        diff = _run_git(["diff", "--name-only", "main", "HEAD"], repo_root)
        if diff is None:
            diff = _run_git(["diff", "--name-only", "origin/main", "HEAD"], repo_root)
        if diff is None:
            return result
        changed = [f for f in diff.strip().split("\n") if f.endswith(".py") and "/tests/" not in f]
        for rp in changed:
            fp = repo_root / rp
            if not fp.exists(): continue
            with open(fp) as fh: cur_api = _extract_public_api(fh.read())
            base = _run_git(["show", f"main:{rp}"], repo_root)
            if base is None: base = _run_git(["show", f"origin/main:{rp}"], repo_root)
            if base is None: continue
            base_api = _extract_public_api(base)
            for cn, bc in base_api.items():
                if cn not in cur_api:
                    c += 1; result.add(severity="CRITICAL", code=f"AR-{c:03d}", rule="A",
                        group="api_regression", category="CLASS_REMOVED",
                        message=f"Public class '{cn}' was removed", file=rp, line=bc.get("line",0),
                        fix_hint=f"Restore '{cn}' or add deprecation shim")
                    continue
                cc = cur_api[cn]
                for mn, bm in bc["methods"].items():
                    if mn not in cc["methods"]:
                        c += 1; result.add(severity="CRITICAL", code=f"AR-{c:03d}", rule="B",
                            group="api_regression", category="METHOD_REMOVED",
                            message=f"Public method '{cn}.{mn}' was removed", file=rp, line=0,
                            fix_hint=f"Restore '{mn}' or add deprecation alias")
                        continue
                    cm = cc["methods"][mn]
                    if bm["args"] != cm["args"]:
                        c += 1; result.add(severity="HIGH", code=f"AR-{c:03d}", rule="C",
                            group="api_regression", category="SIGNATURE_CHANGED",
                            message=f"Signature changed: {cn}.{mn}({', '.join(bm['args'])}) -> ({', '.join(cm['args'])})",
                            file=rp, line=0, fix_hint="Update METHODSIGNATURES.md + all callers",
                            suggestions=[f"Old: {bm['args']}"])
                    if bm["returns"] and cm["returns"] and bm["returns"] != cm["returns"]:
                        c += 1; result.add(severity="HIGH", code=f"AR-{c:03d}", rule="D",
                            group="api_regression", category="RETURN_TYPE_CHANGED",
                            message=f"Return type changed: {cn}.{mn} {bm['returns']} -> {cm['returns']}",
                            file=rp, line=0, fix_hint="Update RETURNVALUES.md + all callers")
        return result
