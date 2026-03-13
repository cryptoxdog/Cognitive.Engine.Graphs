"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [audit]
tags: [L9_TEMPLATE, auditors, api]
owner: platform
status: active
--- /L9_META ---

API Regression Auditor — detects breaking changes vs main branch.
Prevents: Rule 7 (constructor signature drift), Rule 8 (payload contract drift)
Bug Classes: A) CLASS_REMOVED (CRITICAL), B) METHOD_REMOVED (CRITICAL),
             C) SIGNATURE_CHANGED (HIGH), D) RETURN_TYPE_CHANGED (HIGH)
"""

import ast
import subprocess

from tools.auditors.base import (
    AuditorScope,
    AuditResult,
    AuditTier,
    BaseAuditor,
    register_auditor,
)


def _run_git(args: list[str], cwd: str | None) -> str | None:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=30, check=True)
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
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
    def name(self):
        return "api_regression"

    @property
    def domain(self):
        return "universal"

    @property
    def tier(self):
        return AuditTier.REGRESSION

    @property
    def scope(self):
        return AuditorScope(
            include=["engine/**/*.py"],
            exclude=["__pycache__", "tests/"],
            rationale="Public engine API — breaking changes crash downstream callers",
        )

    @property
    def contract_file(self):
        return "docs/contracts/METHODSIGNATURES.md"

    @property
    def requires(self):
        return ["git"]

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        """
        Detects breaking changes in public Python APIs between the current HEAD and the main branch and returns an AuditResult containing any found regressions.
        
        Compares the public API (top-level non-underscore classes and their visible methods) of changed .py files (excluding tests/) between HEAD and main (falling back to origin/main). For each file, records issues for removed public classes, removed public methods, changed method signatures (argument list), and changed return annotations. Issue severities and categories reflect the type of regression (e.g., CRITICAL for removals, HIGH for signature/return changes); unique codes of the form `AR-###` are assigned incrementally.
        
        Parameters:
            files: (unused) placeholder parameter for auditor interface compatibility.
            repo_root: Path to the repository root used to run Git commands and locate files.
            index: Optional index object (not used).
            dep_indexes: Optional dependency indexes (not used).
        
        Returns:
            AuditResult: an audit result populated with any detected API-regression issues.
        """
        result = AuditResult(auditor_name=self.name)
        c = 0
        diff = _run_git(["diff", "--name-only", "main", "HEAD"], repo_root)
        if diff is None:  # nosemgrep: singleton-requires-lock
            diff = _run_git(["diff", "--name-only", "origin/main", "HEAD"], repo_root)
        if diff is None:  # nosemgrep: singleton-requires-lock
            return result
        changed = [f for f in diff.strip().split("\n") if f.endswith(".py") and "/tests/" not in f]
        for rp in changed:
            fp = repo_root / rp
            if not fp.exists():
                continue
            with open(fp) as fh:
                cur_api = _extract_public_api(fh.read())
            base = _run_git(["show", f"main:{rp}"], repo_root)
            if base is None:  # nosemgrep: singleton-requires-lock
                base = _run_git(["show", f"origin/main:{rp}"], repo_root)
            if base is None:  # nosemgrep: singleton-requires-lock
                continue
            base_api = _extract_public_api(base)
            for cn, bc in base_api.items():
                if cn not in cur_api:
                    c += 1
                    result.add(
                        severity="CRITICAL",
                        code=f"AR-{c:03d}",
                        rule="A",
                        group="api_regression",
                        category="CLASS_REMOVED",
                        message=f"Public class '{cn}' was removed",
                        file=rp,
                        line=bc.get("line", 0),
                        fix_hint=f"Restore '{cn}' or add deprecation shim",
                    )
                    continue
                cc = cur_api[cn]
                for mn, bm in bc["methods"].items():
                    if mn not in cc["methods"]:
                        c += 1
                        result.add(
                            severity="CRITICAL",
                            code=f"AR-{c:03d}",
                            rule="B",
                            group="api_regression",
                            category="METHOD_REMOVED",
                            message=f"Public method '{cn}.{mn}' was removed",
                            file=rp,
                            line=0,
                            fix_hint=f"Restore '{mn}' or add deprecation alias",
                        )
                        continue
                    cm = cc["methods"][mn]
                    if bm["args"] != cm["args"]:
                        c += 1
                        result.add(
                            severity="HIGH",
                            code=f"AR-{c:03d}",
                            rule="C",
                            group="api_regression",
                            category="SIGNATURE_CHANGED",
                            message=f"Signature changed: {cn}.{mn}({', '.join(bm['args'])}) -> ({', '.join(cm['args'])})",
                            file=rp,
                            line=0,
                            fix_hint="Update METHODSIGNATURES.md + all callers",
                            suggestions=[f"Old: {bm['args']}"],
                        )
                    if bm["returns"] and cm["returns"] and bm["returns"] != cm["returns"]:
                        c += 1
                        result.add(
                            severity="HIGH",
                            code=f"AR-{c:03d}",
                            rule="D",
                            group="api_regression",
                            category="RETURN_TYPE_CHANGED",
                            message=f"Return type changed: {cn}.{mn} {bm['returns']} -> {cm['returns']}",
                            file=rp,
                            line=0,
                            fix_hint="Update RETURNVALUES.md + all callers",
                        )
        return result
