You are a small implementation agent. Return only the Python implementation in a fenced code block.

Implement:
`shipping_band(total: int) -> str`

Requirements:
- totals below 500 return `"small"`
- totals from 500 through 999 inclusive return `"free"`
- totals of 1000 or more return `"priority"`
- no external dependencies
