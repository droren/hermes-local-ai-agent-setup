You are a test-design agent. Return JSON only.

Requirement:
`normalize_age(age: int) -> int` must accept values from 18 through 120 inclusive. Values below 18 or above 120 must raise `ValueError`. Valid values must be returned unchanged.

Design the minimum useful regression-test set that covers both valid boundaries and both invalid ranges.

Required schema:
{
  "tests": [
    {"name": "...", "input": 18, "expected": "...", "reason": "..."}
  ],
  "coverage_note": "one short sentence"
}
