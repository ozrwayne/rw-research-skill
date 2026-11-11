# Cross-model validation protocol

## Scope

This protocol checks whether the same public Skill instructions produce the required behavior across model providers. It does not measure research outcomes.

The matrix covers:

- `rw-claim-audit`;
- `rw-revision-patch`;
- `rw-research-passport`;
- `rw-research-router` decisions.

The current local model configuration contains Codex `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`, plus Claude `claude-opus-4-8`. Every recorded run freezes the model configuration hash. Historical runs remain evidence for the model configuration saved in their own result file, not for the current default file.

`development-fixtures-v1.json` records the first matrix used to find specification gaps. It is not held-out evidence after those gaps were inspected. `fixtures.json` is the second suite. Its file hash is frozen in each run before model calls start.

## Design

- Run every synthetic fixture once with Skill context and once without Skill context.
- Use the same task text and JSON schema in both conditions.
- Do not include `cases.md`, `behavior-tests.json`, `acceptance.md`, or expected checks in model context.
- Randomize run order with a recorded seed.
- Disable model tools and network tools inside the evaluated turn.
- Score parsed JSON with deterministic checks. No evaluated model acts as Judge.
- Record requested model, provider, CLI version, prompt hash, Skill-context hash, output, duration, token fields, cost fields when supplied, and check results.
- Refuse to overwrite an existing run ID.

If a held-out suite exposes a Skill or scoring defect, keep that run as a development record. Fix the defect, create a new suite, and use a new run ID. Do not change checks after seeing model outputs and then report the same suite as held-out.

## Claim ceiling

A run can show cross-model behavior consistency for the included fixtures. It cannot show that the package improves real research outcomes, generalizes to untested disciplines, or works on model versions that were not run.

`CROSS_MODEL_VERIFIED` requires:

- at least 2 providers and 3 models;
- no parse or execution failures in the Skill condition;
- Skill-condition pass rate of at least 80%;
- every fixture passing on at least 75% of tested models.

Skill increment is reported separately as the pass-rate difference between `with_skill` and `without_skill`.

Real-document review is governed by `document-review-protocol.md`. It is not scored as package conformance and cannot receive `CROSS_MODEL_VERIFIED`.
