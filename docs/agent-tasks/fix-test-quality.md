# Task: Fix Test Quality Finding

```
task: Fix test quality finding "<finding_code>"
tier: 1
contracts_to_read:
  - docs/contracts/TEST_QUALITY.md
  - docs/contracts/TESTPATTERNS.md
```

## Steps by Category

### WEAK_TEST (zero assertions)
- Understand what the test verifies
- Add assertEqual/assertTrue/assertIn/assertRaises
- Every test must assert return value, side effect, or exception

### EMPTY_TEST_FILE
- Add test functions or delete the file
- Minimum: test_happy_path + test_error_path

### HANDLER_UNTESTED
- Create tests/test_{handler}.py
- Test happy path + invalid payload

### FIXTURE_BROKEN
- Replace `Path("./domains")` with `Path(__file__).parent.parent / "domains"`
- Verify fixture instantiates correctly

## Acceptance
- [ ] Finding gone from audit output
- [ ] `pytest tests/ -x` passes
- [ ] `make agent-check` exits 0
