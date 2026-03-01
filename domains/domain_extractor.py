#!/usr/bin/env python3
"""
domain_extractor.py

Extract individual domain specs from ALL_DOMAINS_CONSOLIDATED.yaml
Creates proper directory structure under domains/

USAGE:
    python domain_extractor.py

OUTPUT:
    domains/
    ├── plasticos/spec.yaml
    ├── mortgage-brokerage/spec.yaml
    ├── healthcare-referral/spec.yaml
    ├── freight-matching/spec.yaml
    ├── roofing-company/spec.yaml
    ├── executive-assistant/spec.yaml
    ├── research-agent/spec.yaml
    ├── aios-god-agent/spec.yaml
    ├── repo-as-agent/spec.yaml
    └── legal-discovery/spec.yaml
"""

import re
from pathlib import Path

# Read consolidated file
with open("ALL_DOMAINS_CONSOLIDATED.yaml") as f:
    content = f.read()

# Extract each domain section
domain_pattern = r"# DOMAIN \d+: (.*?)\n# =+\n(.*?)(?=\n# =+\n# DOMAIN \d+:|# =+\n# END OF ALL)"
domains = re.findall(domain_pattern, content, re.DOTALL)

print(f"Found {len(domains)} domain sections")

# Create domains directory
Path("domains").mkdir(exist_ok=True)

# Process each domain
for title, spec in domains:
    # Extract domain ID from YAML
    domain_id_match = re.search(r"domain:\s+id:\s+([a-z0-9-]+)", spec)
    if not domain_id_match:
        print(f"WARNING: Could not find domain ID in {title}, skipping")
        continue

    domain_id = domain_id_match.group(1)

    # Special handling for plasticos (use artifact 72)
    if domain_id == "plasticos":
        print("⚠️  PLASTICOS: Use previously generated artifact 72 (2116-line spec)")
        continue

    # Create domain directory
    domain_dir = Path(f"domains/{domain_id}")
    domain_dir.mkdir(parents=True, exist_ok=True)

    # Clean up YAML (remove --- separator if at start)
    spec_clean = spec.strip()
    if spec_clean.startswith("---"):
        spec_clean = spec_clean[3:].lstrip()

    # Write spec.yaml
    spec_path = domain_dir / "spec.yaml"
    with open(spec_path, "w") as f:
        f.write(spec_clean)

    print(f"✅ Created: {spec_path} ({len(spec_clean)} bytes)")

print("\n🎉 Domain extraction complete!")
print("\nNext steps:")
print("1. Copy plasticos/spec.yaml from artifact 72 (2116-line version)")
print("2. Validate all specs: curl http://localhost:8000/v1/domains")
print("3. Test each domain with sample queries")
