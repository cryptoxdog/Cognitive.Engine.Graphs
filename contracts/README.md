# Machine-Readable Contract Specifications

Each YAML file defines one CEG contract with:
- **id**: Unique contract identifier
- **name**: Human-readable name
- **layer**: Which governance layer (chassis, packet, security, engine, testing, intelligence, hardening)
- **level**: MUST (violation = blocked) or SHOULD (quality measure)
- **scope.paths**: Which files this contract applies to
- **preconditions**: What triggers this contract
- **postconditions**: What must be true after
- **verification.scanner_rules**: contract_scanner.py rule IDs
- **verification.test**: Test file(s) that verify this contract

## Usage

These specs are both documentation and the source of truth for `tools/contract_report.py`.
Run `python tools/contract_report.py` to generate a coverage matrix showing which contracts
have static checks, unit tests, integration tests, and property tests.
