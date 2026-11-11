# Cross-model validation: 2026-07-20-cross-model-v1

Status: `CROSS_MODEL_NOT_VERIFIED`

Providers: claude, codex
Models: anthropic-claude-opus, anthropic-claude-sonnet, openai-gpt-5.6-sol, openai-gpt-5.6-terra
With Skill pass rate: 81.2%
Without Skill pass rate: 50.0%
Paired delta: +31.2%
Minimum fixture pass rate across models: 0.0%

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
| anthropic-claude-opus | with_skill | 6/8 | 75.0% | 90.6% | 12452 ms | $1.1936 | 0 |
| anthropic-claude-opus | without_skill | 4/8 | 50.0% | 68.8% | 10012 ms | $0.8883 | 0 |
| anthropic-claude-sonnet | with_skill | 7/8 | 87.5% | 87.5% | 13940 ms | $0.6408 | 0 |
| anthropic-claude-sonnet | without_skill | 4/8 | 50.0% | 65.6% | 11180 ms | $0.4850 | 0 |
| openai-gpt-5.6-sol | with_skill | 7/8 | 87.5% | 93.8% | 5801 ms | not reported | 0 |
| openai-gpt-5.6-sol | without_skill | 4/8 | 50.0% | 68.8% | 6930 ms | not reported | 0 |
| openai-gpt-5.6-terra | with_skill | 6/8 | 75.0% | 84.4% | 7446 ms | not reported | 0 |
| openai-gpt-5.6-terra | without_skill | 4/8 | 50.0% | 65.6% | 6304 ms | not reported | 0 |

## Fixture consistency

| Fixture | Passed models | Pass rate |
| --- | ---: | ---: |
| claim-full-text-unavailable | 4/4 | 100.0% |
| claim-relative-reduction-mismatch | 4/4 | 100.0% |
| passport-handoff-missing-material | 4/4 | 100.0% |
| passport-material-hash-changed | 2/4 | 50.0% |
| revision-one-of-five-blocks | 4/4 | 100.0% |
| revision-stale-block-hash | 4/4 | 100.0% |
| router-citation-format-only | 0/4 | 0.0% |
| router-technical-replicates | 4/4 | 100.0% |

## Provider-reported model usage

- anthropic-claude-opus: claude-haiku-4-5-20251001, claude-opus-4-8
- anthropic-claude-sonnet: claude-haiku-4-5-20251001, claude-sonnet-4-6

## Boundary

This result applies only to the recorded models, versions, fixtures, prompts, and run configuration. It does not prove improvement in real research outcomes or untested disciplines.
