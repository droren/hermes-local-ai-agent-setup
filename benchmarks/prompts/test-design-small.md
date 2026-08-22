You are a test-design agent. Return JSON only.

Requirement:
A Python function `normalize_discount(discount: int) -> int` must accept values from 0 through 100 inclusive. Values below 0 or above 100 must raise `ValueError`. Valid values must be returned unchanged.

Design the minimum useful regression-test set that covers boundaries and invalid input ranges.

Required schema:
{
  "tests": [
    {"name": "...", "input": 0, "expected": "...", "reason": "..."}
  ],
  "coverage_note": "one short sentence"
}
