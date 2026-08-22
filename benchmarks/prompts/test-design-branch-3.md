You are a test-design agent. Return JSON only.

Requirement:
`shipping_band(total: int) -> str` returns `"small"` for totals below 500, `"free"` for totals from 500 through 999 inclusive, and `"priority"` for totals of 1000 or more.

Design the minimum useful regression-test set covering every branch and both boundaries.

Required schema:
{
  "tests": [
    {"name": "...", "input": 499, "expected": "...", "reason": "..."}
  ],
  "coverage_note": "one short sentence"
}
