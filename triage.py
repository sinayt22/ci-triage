import json
from typing import get_args

from schema import EvalCase, Label
from providers import get_provider
from errors import ClassificationParseError

SYSTEM_PROMPT = """
You are a CI failure triage assistant. Classify why a CI run failed
based on the log excerpt and, if provided:
- a summary of the code diff in that PR.
- the workflow config to determine what was the configuration.
- the failed step.
- the trigger: the event, the branch, the attempt number.

Choose exactly one lable from this set:
- flaky-test: the failure looks unrelated to the diff and non-deterministic (timing, ordering, external falkiness)
- dependency-or-env: a missing/incompatible package, binary, or environment issue
- real-regression: the diff plausibly caused this failure
- infra-timeout: the CI runner, network, or infrastructure timed out or was unreachable
- config-error: a config file, env var, or credential is missing or malformed
- unknown: none of the above clearly apply, or there isn't enough information to decide

Respond with ONLY a JSON object, no other text:
{"label": "<one of the labels above>", "reasoning": "<one sentence>"}

"""

_provider = None

def _get_provider():
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider

def render_case(case: EvalCase) -> str:
    """Render the fields the classifier is allowed to see.
    
    Absend fields say so explicitly. 
    """

    return "\n\n".join([
        f"FAILED STEP:\n{case.failed_step_name or '(not provided)'}",
        f"TRIGGER: event={case.event or '?'} attempt={case.run_attempt or '?'} branch={case.head_branch or '?'}",
        f"DIFF SUMMARY:\n{case.diff_summary or '(not provided)'}",
        f"WORKFLOW CONFIG:\n{case.workflow_config or '(not provided)'}",
        f"LOG EXCERPT:\n{case.log_excerpt}"
    ])


def classify(case: EvalCase) -> str:
    provider = _get_provider()
    raw = provider.complete(SYSTEM_PROMPT, render_case(case)).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ClassificationParseError(raw, "response was not a valid JSON") from e

    label = parsed.get("label")
    if label not in get_args(Label):
        raise ClassificationParseError(raw, f"label {label!r} is not in the allowed set")

    return label