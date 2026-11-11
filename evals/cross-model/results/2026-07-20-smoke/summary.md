# Cross-model validation: 2026-07-20-smoke

Status: `CROSS_MODEL_NOT_VERIFIED`

Providers: claude, codex
Models: anthropic-claude-sonnet, openai-gpt-5.6-terra
With Skill pass rate: 100.0%
Without Skill pass rate: 50.0%
Paired delta: +50.0%
Minimum fixture pass rate across models: 100.0%

## Run record

Source revision: `f5f27d504a74e1e22a3a3fb846f406d8408fafb7`
Worktree dirty at run start: `not recorded`
Fixture file: `not recorded`
Fixture SHA-256: `not recorded`
Model-config SHA-256: `not recorded`
CLI versions: `{"claude": "2.1.157 (Claude Code)", "codex": "codex-cli 0.144.6"}`

## Model results

| Model | Condition | Passed | Pass rate | Mean check score | Median duration | Reported cost | Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| anthropic-claude-sonnet | with_skill | 1/1 | 100.0% | 100.0% | 12446 ms | $0.0932 | 0 |
| anthropic-claude-sonnet | without_skill | 1/1 | 100.0% | 100.0% | 11135 ms | $0.0397 | 0 |
| openai-gpt-5.6-terra | with_skill | 1/1 | 100.0% | 100.0% | 13495 ms | not reported | 0 |
| openai-gpt-5.6-terra | without_skill | 0/1 | 0.0% | 83.3% | 8611 ms | not reported | 0 |

## Fixture consistency

| Fixture | Passed models | Pass rate |
| --- | ---: | ---: |
| claim-relative-reduction-mismatch | 2/2 | 100.0% |

## Provider-reported model usage

- anthropic-claude-sonnet: claude-haiku-4-5-20251001, claude-sonnet-4-6

## Boundary

This result applies only to the recorded models, versions, fixtures, prompts, and run configuration. It does not prove improvement in real research outcomes or untested disciplines.
