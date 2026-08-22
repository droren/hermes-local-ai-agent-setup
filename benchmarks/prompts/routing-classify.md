You are a routing agent. Return JSON only.

Classify the following development request into exactly one primary capability and estimate complexity as small, medium, or large.

Allowed capabilities:
- routing.classify
- planning.decomposition
- code.implement.small
- code.implement
- code.review
- test.design
- research.web.current

Request:
"The PHP checkout currently calculates freight in the controller. Move the calculation behind the existing ShippingService without changing API output, add regression tests for Denmark and Germany, and update the developer note."

Required schema:
{
  "capability": "...",
  "complexity": "...",
  "needs_decomposition": true,
  "reason": "one short sentence"
}
