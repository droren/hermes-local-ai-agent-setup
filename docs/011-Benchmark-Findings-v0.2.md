# 011 - Benchmark Findings v0.2

Status: Preliminary

## Current conclusion

The first local capability benchmarks strongly favor a split between a very small utility model and a very small general code/test model.

### Preliminary defaults

- `qwen3:1.7b`
  - `routing.classify`
  - `summarization.compact`
  - `structured_output` (validated on corrected fixture)

- `granite3.3:2b`
  - `test.design`
  - `code.review`
  - `code.implement.small`
  - `structured_output`

### Current fallback/escalation

- `ministral-3:3b`
  - viable secondary candidate for `test.design`, `code.review`, and `code.implement.small`
  - currently slower than Granite 3.3 2B on measured wall-clock time

- `granite-code:8b`
  - still useful as a larger local fallback for implementation/review
  - failed the current `test.design` fixture due repetitive runaway output before output limiting was added

## Measured comparison: test.design

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 2.862 s | 115.1 | 316 |
| ministral-3:3b | 100 | 4.557 s | 86.4 | 220 |
| phi4-mini:3.8b | 0 | 3.070 s | 81.2 | 154 |
| qwen3.5:2b | 0 | 4.560 s | 89.6 | 384 |

## Measured comparison: code.review

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 2.811 s | 36.4 | 90 |
| ministral-3:3b | 100 | 6.192 s | 77.7 | 225 |

Granite 3.3 2B wins on end-to-end latency despite lower generation throughput because it reaches an accepted answer using substantially fewer output tokens.

## Measured comparison: structured_output

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 1.754 s | 115.3 | 49 |
| ministral-3:3b | 84 | 2.492 s | 87.3 | 47 |

## Measured comparison: code.implement.small

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 0.768 s | 113.8 | 58 |
| ministral-3:3b | 100 | 0.900 s | 90.3 | 53 |

## Interpretation

The 2B Granite model currently looks more useful than the larger 8B Granite Code model for several bounded agent roles. This is exactly why Hermes Next must route by measured capability instead of parameter count or model family naming.

The measured default should remain provisional until each promoted capability has multiple fixtures representing different task shapes. One perfect score on one fixture is evidence, not proof.

## Promotion rule

A model should not become a stable production mapping until it has:

1. at least three independent benchmark fixtures for that capability;
2. no hard failures across those fixtures;
3. acceptable latency on the target host;
4. at least one real-project shadow run reviewed by a human;
5. repeatable results across multiple runs.

## Next benchmark work

Expand the suite for:

- `routing.classify`
- `structured_output`
- `code.implement.small`
- `code.review`
- `test.design`

Then benchmark concurrency: run the proposed `qwen3:1.7b` utility agent and `granite3.3:2b` worker simultaneously and measure latency degradation, unified-memory pressure, and scheduling behavior.
