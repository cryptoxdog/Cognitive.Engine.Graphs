"""Log Safety Auditor — catches sensitive data in log/print statements.
Bug Classes: A) SENSITIVE_LOGGED (HIGH), B) CREDENTIAL_PRINT (HIGH), C) STACK_TRACE_LEAK (MEDIUM)
"""
import re
from pathlib import Path
from typing import Any
from tools.auditors.base import (
    AuditResult, AuditTier, AuditorScope, BaseAuditor, register_auditor,
)

SENSITIVE = ["password","passwd","secret","api_key","apikey","api_secret",
    "token","access_token","refresh_token","auth_token","private_key",
    "credit_card","ssn","neo4j_password","pg_password","db_password"]
LOG_RE = re.compile(r'(?:_?logger|logging)\s*\.\s*(?:debug|info|warning|error|critical|exception)\s*\(', re.I)
PRINT_RE = re.compile(r'\bprint\s*\(')

@register_auditor
class LogSafetyAuditor(BaseAuditor):
    @property
    def name(self): return "log_safety"
    @property
    def domain(self): return "universal"
    @property
    def tier(self): return AuditTier.STATIC
    @property
    def scope(self):
        return AuditorScope(include=["engine/**/*.py","tools/**/*.py"],
            exclude=["__pycache__","tests/"],
            rationale="Sensitive data in logs is a security breach vector")
    @property
    def contract_file(self): return "docs/contracts/ERRORHANDLING.md"

    def scan(self, files, repo_root, index=None, dep_indexes=None):
        result = AuditResult(auditor_name=self.name)
        c = 0
        for pf in files:
            if pf.suffix != ".py": continue
            try:
                with open(pf) as f: lines = f.readlines()
            except: continue
            rel = str(pf.relative_to(repo_root))
            for i, line in enumerate(lines, 1):
                il, ip = LOG_RE.search(line), PRINT_RE.search(line)
                if not (il or ip): continue
                if line.lstrip().startswith("#"): continue
                ll = line.lower()
                for tok in SENSITIVE:
                    if tok in ll:
                        c += 1
                        result.add(severity="HIGH", code=f"LS-{c:03d}",
                            rule="A" if il else "B", group="log_safety",
                            category="SENSITIVE_LOGGED" if il else "CREDENTIAL_PRINT",
                            message=f"'{tok}' in {'log' if il else 'print'} statement",
                            file=rel, line=i, fix_hint="Mask or remove sensitive fields")
                        break
            for i, line in enumerate(lines, 1):
                if re.search(r'str\s*\(\s*(?:exc|exception|err|error|e)\s*\)', line):
                    if any(kw in line for kw in ("return","response","detail=","message=")):
                        c += 1
                        result.add(severity="MEDIUM", code=f"LS-{c:03d}", rule="C",
                            group="log_safety", category="STACK_TRACE_LEAK",
                            message="str(exception) in response leaks internals",
                            file=rel, line=i,
                            fix_hint="Use generic error message; log exception separately")
        return result
