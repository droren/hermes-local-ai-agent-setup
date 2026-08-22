# 011 - Benchmark Findings v0.2

Status: Preliminary

## Current conclusion

The first local capability benchmarks no longer support a single small all-purpose worker. The stronger architecture is a measured specialist split:

### Preliminary defaults

- `qwen3:1.7b`
  - `routing.classify`
  - `summarization.compact`
  - `structured_output` (validated on corrected fixture)

- `granite3.3:2b`
  - `code.implement.small`
  - `code.review` (provisional; one conditional result across three fixtures)
  - `structured_output`

- `ministral-3:3b`
  - `test.design`
  - test-focused secondary reviewer/fallback

### Current fallback/escalation

- `granite-code:8b`
  - larger local fallback for implementation/review
  - failed the first `test.design` fixture due repetitive runaway output before output limiting was added

## Initial single-fixture comparisons

### test.design

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 2.862 s | 115.1 | 316 |
| ministral-3:3b | 100 | 4.557 s | 86.4 | 220 |
| phi4-mini:3.8b | 0 | 3.070 s | 81.2 | 154 |
| qwen3.5:2b | 0 | 4.560 s | 89.6 | 384 |

### code.review

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 2.811 s | 36.4 | 90 |
| ministral-3:3b | 100 | 6.192 s | 77.7 | 225 |

Granite 3.3 2B wins on end-to-end latency despite lower generation throughput because it reaches an accepted answer using substantially fewer output tokens.

### structured_output

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 1.754 s | 115.3 | 49 |
| ministral-3:3b | 84 | 2.492 s | 87.3 | 47 |

### code.implement.small

| Model | Score | Wall time | Tokens/s | Output tokens |
|---|---:|---:|---:|---:|
| granite3.3:2b | 100 | 0.768 s | 113.8 | 58 |
| ministral-3:3b | 100 | 0.900 s | 90.3 | 53 |

## Robustness suite: three fixtures per capability

The multi-fixture run changed the preferred role split.

### granite3.3:2b

- `code.implement.small`: 100 / 100 / 100
- `code.review`: 100 / 75 / 100
- `test.design`: 100 / 0 / 100

Interpretation:

- excellent bounded implementation candidate;
- strong but not yet fully stable reviewer;
- not robust enough to own `test.design` despite winning the first single fixture.

### ministral-3:3b

- `code.implement.small`: 83.3 / 100 / 100
- `code.review`: 75 / 0 / 100
- `test.design`: 100 / 100 / 100

Interpretation:

- currently the strongest measured dedicated test-design specialist;
- useful implementation fallback;
- review behavior is less reliable than Granite on the current suite.

## Specialist mapping suggested by current evidence

```text
qwen3:1.7b
  routing.classify
  summarization.compact
  structured_output

granite3.3:2b
  code.implement.small
  code.review (provisional)
  structured_output

ministral-3:3b
  test.design
  independent test-oriented validation

granite-code:8b
  larger local escalation for implementation/review
```

This is preferable to assigning every small role to Granite simply because it won several first-round comparisons. The robustness suite demonstrates why Hermes Next must preserve specialist mappings and continue measuring them.

## Two-model concurrency result

Models tested concurrently:

- router: `qwen3:1.7b`
- worker: `granite3.3:2b`
- context: 8192

Three measured runs:

| Run | Sequential | Concurrent |
|---|---:|---:|
| 1 | 2.550 s | 2.132 s |
| 2 | 2.365 s | 2.094 s |
| 3 | 2.330 s | 2.111 s |

Average:

- sequential: 2.415 s
- concurrent: 2.112 s
- effective speedup: 1.143x

The worker remained well behaved in concurrent mode, although generation throughput dropped from roughly 115-119 tok/s sequentially to roughly 80-84 tok/s concurrently.

The router also slowed from roughly 151-155 tok/s to roughly 128-131 tok/s, but more importantly it hit the configured output-token limit (`done_reason=length`) in every measured concurrency run. Therefore the current concurrency test demonstrates that parallel execution is physically viable, but it does **not** yet prove acceptable concurrent routing quality.

## Concurrency interpretation

Current evidence supports keeping both small models resident and permitting bounded parallel work. The observed 14.3% effective wall-time gain is useful, but throughput degradation confirms that GPU/shared-memory scheduling is not free.

Hermes scheduling should eventually consider:

- whether two jobs are latency-sensitive;
- current resident model set;
- expected output size;
- whether a capability can tolerate reduced generation throughput;
- whether adding a third concurrent specialist produces useful aggregate throughput or only contention.

Do not promote an unlimited parallel-agent policy from this result.

## Promotion rule

A model should not become a stable production mapping until it has:

1. at least three independent benchmark fixtures for that capability;
2. no hard failures across those fixtures;
3. acceptable latency on the target host;
4. at least one real-project shadow run reviewed by a human;
5. repeatable results across multiple runs.

Under this rule today:

- `granite3.3:2b` is eligible for promotion as `code.implement.small` candidate, pending real-project shadow runs and repeatability;
- `ministral-3:3b` is eligible for promotion as `test.design` candidate, pending real-project shadow runs and repeatability;
- `granite3.3:2b` should remain provisional for `code.review`;
- neither small model has passed the rule for every capability it has tested.

## Next benchmark work

1. Fix the concurrency router workload so it completes with `done_reason=stop`.
2. Repeat two-model concurrency and compare quality as well as wall time.
3. Add three-fixture robustness suites for `routing.classify` and `structured_output`.
4. Run real-project shadow tasks for Granite implementation and Ministral test design.
5. If two-model concurrency remains healthy, test the three-specialist set (`qwen3:1.7b` + `granite3.3:2b` + `ministral-3:3b`) before deciding a host concurrency limit.
