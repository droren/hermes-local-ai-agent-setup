You are an independent code reviewer. Do not rewrite the code. Identify defects and return JSON only.

Task requirement:
A function must return the discounted integer price. Discounts below 0 are invalid. Discounts above 100 are invalid. A 100 percent discount must return 0.

Candidate implementation:
```python
def discounted_price(price: int, discount: int) -> int:
    if discount < 0 or discount >= 100:
        raise ValueError("invalid discount")
    return int(price * ((100 - discount) / 100))
```

Required schema:
{
  "pass": false,
  "defects": [
    {"severity": "...", "description": "..."}
  ],
  "missing_tests": ["..."]
}
