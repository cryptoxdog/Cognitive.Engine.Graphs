#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [tools]
tags: [L9_TEMPLATE, tools, domain-extractor]
owner: platform
status: active
--- /L9_META ---

domain_extractor.py

Extract individual domain specs from a consolidated YAML file.
Creates proper directory structure under domains/

USAGE:
    python tools/domain_extractor.py <consolidated_file.yaml>
    python tools/domain_extractor.py domains/MASTER-SPEC-ALL-DOMAINS.yaml

OUTPUT:
    domains/
    ├── plasticos_domain_spec.yaml
    ├── mortgage_brokerage_domain_spec.yaml
    ├── healthcare_referral_domain_spec.yaml
    └── ...
"""

import re
import sys
from pathlib import Path


def extract_domains(input_file: Path) -> None:
    """Extract individual domain specs from consolidated file."""
    if not input_file.exists():
        print(f"ERROR: File not found: {input_file}")
        sys.exit(1)

    content = input_file.read_text()

    # Extract each domain section
    domain_pattern = r"# DOMAIN \d+: (.*?)\n# =+\n(.*?)(?=\n# =+\n# DOMAIN \d+:|# =+\n# END OF ALL|$)"
    domains = re.findall(domain_pattern, content, re.DOTALL)

    if not domains:
        print("WARNING: No domain sections found. Expected format:")
        print("  # DOMAIN 1: Domain Name")
        print("  # =====================")
        print("  <yaml content>")
        sys.exit(1)

    print(f"Found {len(domains)} domain sections")

    # Create domains directory
    domains_dir = Path("domains")
    domains_dir.mkdir(exist_ok=True)

    # Process each domain
    for title, spec in domains:
        # Extract domain ID from YAML
        domain_id_match = re.search(r"domain:\s+id:\s+([a-z0-9_-]+)", spec)
        if not domain_id_match:
            print(f"WARNING: Could not find domain ID in {title}, skipping")
            continue

        domain_id = domain_id_match.group(1)

        # Normalize domain_id (replace hyphens with underscores for filename)
        domain_id_normalized = domain_id.replace("-", "_")

        # Clean up YAML (remove --- separator if at start)
        spec_clean = spec.strip()
        if spec_clean.startswith("---"):
            spec_clean = spec_clean[3:].lstrip()

        # Write spec file with standard naming convention
        spec_path = domains_dir / f"{domain_id_normalized}_domain_spec.yaml"
        spec_path.write_text(spec_clean)

        print(f"✅ Created: {spec_path} ({len(spec_clean)} bytes)")

    print("\n🎉 Domain extraction complete!")
    print("\nNext steps:")
    print("1. Validate all specs: curl http://localhost:8000/v1/domains")
    print("2. Test each domain with sample queries")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/domain_extractor.py <consolidated_file.yaml>")
        print("\nExample:")
        print("  python tools/domain_extractor.py domains/MASTER-SPEC-ALL-DOMAINS.yaml")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    extract_domains(input_file)


if __name__ == "__main__":
    main()
