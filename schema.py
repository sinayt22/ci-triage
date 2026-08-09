from pydantic import BaseModel
from typing import Literal

Label = Literal[
    "flaky-test",
    "dependency-or-env",
    "real-regression",
    "infra-timeout",
    "config-error",
    "unknown"
]

class EvalCase(BaseModel):
    id: str
    repo: str
    log_excerpt: str # the input your system sees
    diff_summary: str | None
    label: Label # ground-truth
    notes: str = "" # why labelled it this way
