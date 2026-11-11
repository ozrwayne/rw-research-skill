# Cross-model validation: 2026-07-20-cross-model-v2

Status: `CROSS_MODEL_VERIFIED`

Providers: claude, codex
Models: anthropic-claude-opus, anthropic-claude-sonnet, openai-gpt-5.6-sol, openai-gpt-5.6-terra
With Skill pass rate: 100.0%
Without Skill pass rate: 59.4%
Paired delta: +40.6%
Minimum fixture pass rate across models: 100.0%

## Run record

Source revision: `f5f27d504a74e1e22a3a3fb846f406d8408fafb7`
Worktree dirty at run start: `True`
Fixture file: `fixtures.json`
Fixture SHA-256: `01e04c2e6769fecd36d0c4415816fccbf1c981aad4982a18d0fabe0f6f43cb5b`
Model-config SHA-256: `ac3da70959b21d93c7c461748645bf936f88bc39ffa4cc4294a1724713aa126a`
CLI versions: `{"claude": "2.1.157 (Claude Code)", "codex": "codex-cli 0.144.6"}`

## Model results

| Model | Condition | Passed | Pass rate | Mean check score | Median duration | Reported cost | Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| anthropic-claude-opus | with_skill | 8/8 | 100.0% | 100.0% | 13290 ms | $1.1878 | 0 |
| anthropic-claude-opus | without_skill | 5/8 | 62.5% | 68.8% | 10196 ms | $0.8666 | 0 |
| anthropic-claude-sonnet | with_skill | 8/8 | 100.0% | 100.0% | 13856 ms | $0.6352 | 0 |
| anthropic-claude-sonnet | without_skill | 5/8 | 62.5% | 68.8% | 12150 ms | $0.4666 | 0 |
| openai-gpt-5.6-sol | with_skill | 8/8 | 100.0% | 100.0% | 6310 ms | not reported | 0 |
| openai-gpt-5.6-sol | without_skill | 4/8 | 50.0% | 66.7% | 7850 ms | not reported | 0 |
| openai-gpt-5.6-terra | with_skill | 8/8 | 100.0% | 100.0% | 6509 ms | not reported | 0 |
| openai-gpt-5.6-terra | without_skill | 5/8 | 62.5% | 68.8% | 5596 ms | not reported | 0 |

## Fixture consistency

| Fixture | Passed models | Pass rate |
| --- | ---: | ---: |
| claim-adjusted-effect-mismatch | 4/4 | 100.0% |
| claim-subgroup-fulltext-missing | 4/4 | 100.0% |
| passport-prepared-handoff-missing-id | 4/4 | 100.0% |
| passport-source-version-replaced | 4/4 | 100.0% |
| revision-caption-only | 4/4 | 100.0% |
| revision-three-block-hash-drift | 4/4 | 100.0% |
| router-pseudoreplication-reporting | 4/4 | 100.0% |
| router-reference-identity-only | 4/4 | 100.0% |

## Provider-reported model usage

- anthropic-claude-opus: claude-haiku-4-5-20251001, claude-opus-4-8
- anthropic-claude-sonnet: claude-haiku-4-5-20251001, claude-sonnet-4-6

## Boundary

This result applies only to the recorded models, versions, fixtures, prompts, and run configuration. It does not prove improvement in real research outcomes or untested disciplines.
