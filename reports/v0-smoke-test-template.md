# AI TamperGuard v0 smoke-test report template

## Plumbing diagnostics (not detection quality)

This is not a tamper detector. v0 proves the local-training to operational-scoring plumbing before any detection-quality claim.

## Required private report fields

- model_version
- training git SHA
- label-rule fingerprint
- dataset window summary
- training diagnostics
- holdout split sizes
- deployment write-path used, when deployment is in scope
- MCP validation transcript summary, when deployment is in scope
- G2 anti-degeneracy numbers
- G6 equivalence numbers, when Splunk scoring is in scope
- known limitations

## Claim boundary

Weak proxy labels are working-model plumbing labels, not malicious ground truth.
