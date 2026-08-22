You are an independent code reviewer. Return JSON only.

Requirement:
`is_free_shipping(total: int, country: str) -> bool` must return true only when total is at least 500 and country is either `DK` or `SE`.

Candidate implementation:
```python
def is_free_shipping(total: int, country: str) -> bool:
    return total > 500 and country in {"DK", "SE"}
```

Required schema:
{
  "pass": false,
  "defects": [
    {"severity": "...", "description": "..."}
  ],
  "missing_tests": ["..."]
}
