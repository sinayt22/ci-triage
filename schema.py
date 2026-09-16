from pydantic import BaseModel
from typing import Literal
from enum import StrEnum

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
    failed_step_name: str | None = None
    workflow_config: str | None = None 
    run_attempt: int | None = None
    event: str | None = None
    head_branch: str | None = None
    label: Label # ground-truth
    notes: str = "" # why labelled it this way

class StepSummary(BaseModel):
    name: str | None = None
    number: int | None = None
    conclusion: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class StepsInfo(BaseModel):
    failed_step_name: str | None = None
    failed_step_number: int | None = None
    steps: list[StepSummary] = []

class RunInfo(BaseModel):
    run_id: int
    run_attempt: int | None = None
    event: str | None = None
    head_branch: str | None = None
    head_sha: str | None = None
    run_url: str | None = None
    workflow_name: str | None = None
    workflow_path: str | None = None
    created_at: str | None = None

class LogInfo(BaseModel):
    excerpt: str
    path: str | None = None # relative to the candidates dir
    excerpt_strategy: str

class DiffStatus(StrEnum):
    OK = "ok"
    NO_PR_NO_SHA = "no-pr-no-sha"
    API_ERROR = "api-error"
    NO_FILES = "no-files"

class DiffInfo(BaseModel):
    summary: str | None = None
    status: DiffStatus

class TriageInfo(BaseModel):
    label: None = None
    notes: str = ""
    heuristic_hint: str | None = None

class Candidate(BaseModel):
    id: str
    repo: str
    job_name: str | None = None
    job_url: str | None = None
    created_at: str | None = None
    run: RunInfo
    steps: StepsInfo
    log: LogInfo
    diff: DiffInfo
    workflow_config: str | None = None
    triage: TriageInfo = TriageInfo()


def candidate_to_eval_case(c: Candidate, label: Label, notes: str = "") -> EvalCase:
    return EvalCase(
        id = c.id,
        repo = c.repo,
        log_excerpt = c.log.excerpt,
        diff_summary = c.diff.summary,
        failed_step_name= c.steps.failed_step_name,
        workflow_config = c.workflow_config,
        run_attempt = c.run.run_attempt,
        event = c.run.event,
        head_branch = c.run.head_branch,
        label = label,
        notes = notes
    )