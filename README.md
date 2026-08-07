# CI Failure Triage Agent - Evals

A system that reads a failing CI run (log excerpt + optional diff summary) and
classifies it into one of six causes: `flaky-test`, `dependency-or-env`,
`real-regression`, `infra-timeout`, `config-error`, `unknown`.
This directory tracks the evals that decide whether changes to that system are
actually improvements.

---

## Eval Foundations

### What decision will these evals inform?
- Whether to accept or revert a change to the prompt (system or user message).
- Whether to accept or revert changes to other parameters - tools exposed,
  temperature, output schema.

### What does a bad output look like in this system?
- **Bad format** - output isn't valid according to the expected structure.
- **Parameter/schema validation failure** - a field is missing, `None` when
  it shouldn't be, out of bounds, not drawn from the allowed set, or two
  fields are individually valid but inconsistent with each other. (e.g. a fix
  proposed with confidence 0.9 but not `proposed_fix` text).
- **Guardrail violation** - the system takes a disallowed action, e.g.
  reading a file outside the working directory, or calling a tool it
  shouldn't have access to for this task.
- **Wrong label** - the predicted label doesn't match the hand-assigned
  ground-truth label for that case.
- **Right label, wrong explanation** - the classification is correct but
  the reasoning/justification given for it doesn't actually hold up.
- **Wrong analysis on an open question** - for fields with no single correct
  answer (e.g. free-text root-cause analysis), the reasoning is simply
  incorrect or unsupported by the log, as judged by another model.

### Which check type could catch each?
| # | Bad Output | Check Type | Why |
|---|---|---|---|
| 1 | Bad format | Deterministic | Same structural rule applies to every case; no per-case fact needed. |
| 2 | Paremeter/schema validation failure | Deterministic | Same as above - presence, bounds, enum, and cross-field rules are universal |
| 3 | Guardrail validation | Deterministic | Fixed policy check against the action trace, same rule for every case.
| 4 | Wrong label | Reference-based | Required comparing against the specific hand-assigned ground truth for *this* case. |
| 5 | Right label, wrong explanation | Model-graded | No fixed reference for "explanation quality" - needs judgement.
| 6 | Wrong analysis on open question | Model-graded | No single correct answer exists to compare against - needs judgement. |