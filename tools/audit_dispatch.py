#!/usr/bin/env python3
"""L9 Unified Audit Dispatch v2 — tiered execution, progressive output, PR comments.

Usage:
  python tools/audit_dispatch.py                          # All static auditors
  python tools/audit_dispatch.py --tier static            # Static tier only
  python tools/audit_dispatch.py --tier regression        # Needs git history
  python tools/audit_dispatch.py --domain odoo            # Odoo auditors only
  python tools/audit_dispatch.py --auditor api_regression # Single auditor
  python tools/audit_dispatch.py --strict                 # Exit 1 on blocking
  python tools/audit_dispatch.py --json                   # JSON output
  python tools/audit_dispatch.py --summary                # Top N per severity
  python tools/audit_dispatch.py --pr-comment             # Generate PR comment markdown
  python tools/audit_dispatch.py --list                   # Show registered auditors
"""
import argparse, importlib, json as json_mod, shutil, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.auditors.base import (
    AuditResult, AuditTier,
    get_all_auditors, get_auditor, get_auditors_for_domain, get_auditors_for_tier,
)

# Auto-discover auditor modules
AUDITORS_DIR = REPO_ROOT / "tools" / "auditors"
for py_file in AUDITORS_DIR.glob("*.py"):
    if py_file.name.startswith("_") or py_file.name == "base.py":
        continue
    try:
        importlib.import_module(f"tools.auditors.{py_file.stem}")
    except ImportError as e:
        print(f"WARN: Could not load auditor {py_file.stem}: {e}", file=sys.stderr)


def _check_requirements(auditor) -> bool:
    for req in auditor.requires:
        if req == "git":
            if not shutil.which("git"): return False
            r = subprocess.run(["git", "rev-parse", "--git-dir"],
                               capture_output=True, cwd=REPO_ROOT)
            if r.returncode != 0: return False
        elif req == "postgres":
            try: import psycopg2
            except ImportError: return False
        elif req == "pytest-cov":
            if not (REPO_ROOT / "coverage.json").exists(): return False
    return True


def run_auditor(auditor, repo_root, dep_indexes=None):
    files = auditor.scope.resolve(repo_root)
    if not files:
        return AuditResult(auditor_name=auditor.name)
    index = auditor.prepare(files, repo_root)
    return auditor.scan(files, repo_root, index=index, dep_indexes=dep_indexes)


def print_results(results, summary=False, as_json=False, pr_comment=False):
    all_f = []
    for r in results:
        all_f.extend(r.findings)

    if as_json:
        out = [{"auditor": f.group, "severity": f.severity, "code": f.code,
                "rule": str(f.rule), "category": f.category, "message": f.message,
                "file": f.file, "line": f.line, "fix_hint": f.fix_hint,
                "safe_rewrite": f.safe_rewrite, "suggestions": f.suggestions}
               for f in all_f]
        print(json_mod.dumps(out, indent=2))
        return

    if pr_comment:
        _pr_comment(results, all_f); return

    if not all_f:
        print("All auditors passed. Zero findings.")
        for r in results: print(f"  [{r.auditor_name}] clean")
        return

    by_sev = {"BLOCKER": [], "CRITICAL": [], "HIGH": [], "MEDIUM": [], "INFO": []}
    for f in all_f:
        by_sev.get(f.severity, by_sev["INFO"]).append(f)

    mx = 5 if summary else 999
    for sev in ["BLOCKER", "CRITICAL", "HIGH", "MEDIUM", "INFO"]:
        fs = by_sev[sev]
        if not fs: continue
        print(f"\n{'=' * 60}\n{sev}: {len(fs)} findings\n{'=' * 60}")
        for f in fs[:mx]:
            print(f"  [{f.code}] {f.message}")
            print(f"         {f.file}:{f.line}")
            if f.fix_hint: print(f"         Fix: {f.fix_hint}")
            if f.suggestions: print(f"         Try: {', '.join(f.suggestions)}")
            print()
        if len(fs) > mx: print(f"  ... and {len(fs) - mx} more\n")

    tb = sum(len(by_sev[s]) for s in ("BLOCKER", "CRITICAL"))
    print(f"\nTOTAL: {len(all_f)} findings ({tb} BLOCKER/CRITICAL, {len(by_sev['HIGH'])} HIGH)")


def _pr_comment(results, all_f):
    if not all_f:
        print("## \u2705 Audit Passed\n\nAll auditors passed with zero findings.")
        return
    crit = [f for f in all_f if f.severity in ("BLOCKER", "CRITICAL")]
    high = [f for f in all_f if f.severity == "HIGH"]
    print("## \u274c Audit Failed\n")
    if crit:
        print(f"**{len(crit)} CRITICAL issues:**\n")
        for f in crit[:5]:
            print(f"- **[{f.code}]** {f.message}")
            print(f"  `{f.file}:{f.line}`")
            if f.fix_hint: print(f"  \U0001f4a1 {f.fix_hint}")
    if high:
        print(f"\n**{len(high)} HIGH issues:**\n")
        for f in high[:5]:
            print(f"- **[{f.code}]** {f.message}  `{f.file}:{f.line}`")
    print(f"\n---\n*{len(all_f)} total from {len([r for r in results if r.findings])} auditors*")


def main():
    p = argparse.ArgumentParser(description="L9 Unified Audit Dispatch v2")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--domain", type=str, default=None)
    p.add_argument("--tier", type=str, default=None)
    p.add_argument("--auditor", type=str, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--pr-comment", action="store_true")
    p.add_argument("--list", action="store_true")
    args = p.parse_args()

    if args.list:
        auditors = get_all_auditors()
        print(f"Registered auditors ({len(auditors)}):\n")
        print(f"  {'NAME':<25s} {'DOMAIN':<12s} {'TIER':<12s} CONTRACT")
        print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*40}")
        for a in sorted(auditors, key=lambda x: (x.tier.value, x.domain, x.name)):
            rq = f" [requires: {', '.join(a.requires)}]" if a.requires else ""
            print(f"  {a.name:<25s} {a.domain:<12s} {a.tier.value:<12s} {a.contract_file}{rq}")
        sys.exit(0)

    if args.auditor: auditors = [get_auditor(args.auditor)]
    elif args.tier: auditors = get_auditors_for_tier(AuditTier(args.tier))
    elif args.domain: auditors = get_auditors_for_domain(args.domain)
    else: auditors = get_all_auditors()

    runnable, skipped = [], []
    for a in auditors:
        (runnable if _check_requirements(a) else skipped).append(a)
    if skipped and not args.json:
        for a in skipped:
            print(f"SKIP: [{a.name}] requirements not met: {a.requires}", file=sys.stderr)

    if not runnable:
        print("No runnable auditors. Use --list to see all."); sys.exit(0)

    results, indexes = [], {}
    for auditor in runnable:
        dep_idx = {d: indexes[d] for d in auditor.dependencies if d in indexes}
        r = run_auditor(auditor, REPO_ROOT, dep_indexes=dep_idx or None)
        results.append(r)

    print_results(results, summary=args.summary, as_json=args.json, pr_comment=args.pr_comment)

    if args.strict or args.pr_comment:
        rp = REPO_ROOT / "audit_report.json"
        af = []
        for r in results:
            af.extend([{"auditor":f.group,"severity":f.severity,"code":f.code,
                        "message":f.message,"file":f.file,"line":f.line} for f in r.findings])
        with open(rp, "w") as f: json_mod.dump(af, f, indent=2)

    if args.strict:
        if any(r.has_blocking for r in results):
            print("\nFAIL: Blocking findings detected.", file=sys.stderr); sys.exit(1)
        else:
            print("\nPASS: No blocking findings."); sys.exit(0)


if __name__ == "__main__":
    main()
