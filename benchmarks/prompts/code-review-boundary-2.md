You are an independent code reviewer. Return JSON only.

Requirement:
`clamp_quantity(qty: int) -> int` must accept values from 1 through 99 inclusive. Values below 1 must raise `ValueError`. Values above 99 must raise `ValueError`. Valid values must be returned unchanged.

Candidate implementation:
```python
def clamp_quantity(qty: int) -> int:
    if qty <= 1 or qty > 99:
        raise ValueError("invalid quantity")
    return qty
```

Required schema:
{
  "pass": false,
  "defects": [
    {"severity": "...", "description": "..."}
  ],
  "missing_tests": ["..."]
}
