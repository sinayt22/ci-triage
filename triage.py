import json

from schema import Label
from providers import get_provider
from errors import ClassificationParseError

SYSTEM_PROMPT = """
You are a CI failure triage assistant. Classify why a CI run failed
based on the log excerpt and, if provided, a summary of the code diff in that PR.

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

def classify(log_excerpt: str, diff_summary: str | None = None) -> str:
    provider = _get_provider()
    user_content = (
        f"LOG EXCERPT:\n{log_excerpt}\n\n"
        f"DIFF SUMMARY:\n{diff_summary or '(no diff provided)'}"
    )
    raw = provider.complete(SYSTEM_PROMPT, user_content).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ClassificationParseError(raw, "response was not a valid JSON") from e

    label = parsed.get("label")
    if label not in Label:
        raise ClassificationParseError(raw, f"label {label!r} is not in the allowed set")

    return label