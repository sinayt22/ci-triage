"""
PLACEHOLDER system under test.

This is intentionally NOT a real classifier — no LLM call, no real logic.
It's a dumb keyword heuristic so that evals/run.py has something real to
score. Expect it to be mediocre. just needs a
number and some named misses, not a good system yet.

Will be Replaced with real triage logic (rule-based or LLM-based) later.
"""

def classify(log_excerpt: str, diff_summary: str | None = None) -> str:
    text = log_excerpt.lower()

    if "timeout" in text or "timed out" in text:
        return "infra-timeout"
    if any(k in text for k in ["modulenotfounderror", "npm err", "eresolve", 
                               "command not found"]):
        return "dependency-or-env"
    if any(k in text for k in ["yaml", "keyerror", "nocredentialserror"]):
        return "config-error"
    if "assertionerror" in text:
        return "real-regression"

    return "unknown"