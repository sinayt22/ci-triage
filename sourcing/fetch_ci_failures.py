"""
Pulls real, recent CI failures from a GitHub repo's Actions history into
UNREVIEWD candidate records for later hand-labeling.

This does NOT produce ground truth. Every "label" field here is None on
purpose - the label will be diceided later.

"""

import argparse
from datetime import datetime, timedelta
from functools import lru_cache
import json
import os
import re
import time
from pathlib import Path
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema import *

load_dotenv()

API = "https://api.github.com"
TIMESTAMP_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z")

# Lightweight keyword hints, purely to help human triage faster.
# NOT a classifier, NOT ground truth - see module docstring.

HINT_RULES = [
    ("infra-timeout", ["timed out", "timeout", "connection refused", "connection reset"]),
    ("dependency-or-env", ["modulenotfounderror", "no matching distribution", "resolution-too-deep",
                           "command not found", "eresolve"]),
    ("config-error", ["yaml", "keyerror:", "nocredentialserror", "environment variable"]),
    ("real-regression", ["assertionerror", "traceback (most recent call last)"])
 ]

def heuristic_hint(text:str) -> str | None:
    text = text.lower()
    for label, keywords in HINT_RULES:
        if any(kw in text for kw in keywords):
            return label
    return None

def make_session(token:str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-Github-Api-Version": "2022-11-28"
    })
    return session

def list_failed_runs(repo:str, session: requests.Session, max_runs:int, since:str | None = None):
    runs = []
    page = 1
    params = {"status": "failure", "per_page": 100, "page": page} 
    if since:
        params["created"] = f">={since}"
    while len(runs) < max_runs:
        params["page"] = page
        page += 1
        response = session.get(
            f"{API}/repos/{repo}/actions/runs",
            params=params
        )
        if response.status_code != 200:
            print(f"    ! failed to list runs (page {page}): {response.status_code} {response.text[:200]}")
            break
        batch = response.json().get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
        if len(batch) < 100:
            break

    return runs[:max_runs]

def list_failed_jobs(repo: str, run_id:int, session: requests.Session):
    response = session.get(
        f"{API}/repos/{repo}/actions/runs/{run_id}/jobs")
    if response.status_code != 200:
        return []

    jobs = response.json().get("jobs", [])
    return [j for j in jobs if j.get("conclusion") == "failure"]

def summarize_steps(job: dict) -> dict:
    """Extract step-level outcome from a job paylod.
    
    GitHub returns steps[] on the jobs endpoint. Each has name/number/conclusion
    /started_at/completed_at. The name of the failing step is
    the chepest strong signal we have about where in the job it broke
    (checkout vs setup vs build vs test)
    """

    steps = job.get("steps") or []
    failed = [s for s in steps if s.get("conclusion") == "failure"]
    first_failed = failed[0] if failed else None
    steps_models = [
        StepSummary(
        name = s.get("name"),
        number = s.get("number"),
        conclusion = s.get("conclusion"),
        started_at = s.get("started_at"),
        completed_at = s.get("completed_at"))
        for s in steps
    ]
    return StepsInfo(
        failed_step_name = first_failed.get("name") if first_failed else None,
        failed_step_number = first_failed.get("number") if first_failed else None,
        steps = steps_models
    )
        

def summarize_run(run: dict) -> RunInfo:
    return RunInfo(
        run_id = run.get("id"),
        run_attempt= run.get("run_attempt"),
        event = run.get("event"),
        head_branch = run.get("head_branch"),
        head_sha = run.get("head_sha"),
        run_url = run.get("html_url"),
        workflow_name = run.get("name"),
        workflow_path = run.get("path"),
        created_at = run.get("created_at")
    )


def get_job_log(repo:str, job_id:int, session: requests.Session, out_path:Path, 
                                max_lines:int = 150) -> LogInfo | None:
    
    url = f"{API}/repos/{repo}/actions/jobs/{job_id}/logs"
    response = session.get(url)
    if response.status_code != 200:
        return None

    # save the full log for future reference if needed
    logs_dir = out_path.parent / "logs" / repo.replace('/', '-')
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_path = logs_dir / f"{job_id}.txt"
    file_path.write_text(response.text)

    lines = [TIMESTAMP_PREFIX.sub("", line) for line in response.text.splitlines()]
    tail = lines[-max_lines:]
    log = "\n".join(tail).strip()

    return LogInfo(
        excerpt = log,
        path = str(file_path.relative_to(out_path.parent)),
        excerpt_strategy = f"tail-{max_lines}"
    )

def get_diff_summary(repo:str, run:dict, session:requests.Session, 
                     max_files:int = 5) -> DiffInfo:
    """Summarize the code changes under test
    
    Status distinguishes 'there was genuinely no diff' from 
    'we failed to fetch one'
    """

    prs = run.get("pull_requests") or []
    if prs:
        pr_number = prs[0]["number"]
        response = session.get(f"{API}/repos/{repo}/pulls/{pr_number}/files")
    else:
        sha = run.get("head_sha")
        if not sha:
            return DiffInfo(summary=None, status=DiffStatus.NO_PR_NO_SHA)
        response = session.get(f"{API}/repos/{repo}/commits/{sha}")

    if response.status_code != 200:
        return DiffInfo(summary=None, status=DiffStatus.API_ERROR)

    files = response.json() if prs else response.json().get("files", [])
    if not files:
        return DiffInfo(summary=None, status=DiffStatus.NO_FILES)

    shown = files[:max_files]
    parts = [f"{f['filename']} +{f.get('additions', 0)}/-{f.get('deletions', 0)}" for f in shown]
    summary = f"{len(files)} files(s) changed: " + ", ".join(parts)
    if len(files) > max_files:
        summary += f", + {len(files) - max_files} more"
    return DiffInfo(summary=summary, status=DiffStatus.OK)

def get_workflow_config(repo: str, run: dict, session: requests.Session,
                        max_chars:int = 6000) -> str | None:
    """Fetch the workflow YAML as it existed at the failing commit.
    run['path'] is the workflow file, run['head_sha'] pins it to the commit
    under test - so we see the config that actually produced this failure,
    not whatever main looks like today.
    """

    path = run.get("path")
    ref = run.get("head_sha")
    if not (path and ref):
        return None
    response = session.get(
        f"{API}/repos/{repo}/contents/{path}",
        params={"ref": ref},
        headers={"Accept": "application/vnd.github.raw"}
    )

    if response.status_code != 200:
        return None

    text = response.text
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... (truncated, {len(text)} chars total)"
    return text


def fetch(repo: str, token:str, max_cases:int, out_path:Path, max_per_run: int = 2, since: str = None):
    session = make_session(token)

    print(f"Listing failed runs for {repo} ... ")
    runs = list_failed_runs(repo, session, max_cases * 2, since)
    print(f"    Found {len(runs)} failed run(s) to inspect")

    candidates = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen_ids = set()

    for run in runs:
        if len(candidates) >= max_cases:
            break

        diff = get_diff_summary(repo, run, session)
        workflow_config = get_workflow_config(repo, run, session)

        failed_jobs = list_failed_jobs(repo, run["id"], session)
        if not failed_jobs:
            continue

        run_info = summarize_run(run)

        per_run = 0
        for job in failed_jobs:
            if per_run >= max_per_run:
                break

            candidate_id = f"{repo.replace('/', '-')}-run{run_info.run_id}-job{job["id"]}"
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)

            if len(candidates) >= max_cases:
                break
            job_log = get_job_log(repo, job["id"], session, out_path)
            if not job_log or not job_log.excerpt:
                continue
            
            steps = summarize_steps(job)

            c = Candidate(
                id = candidate_id,
                repo = repo,
                job_name = job.get("name"),
                job_url = job.get("html_url"),
                created_at = run_info.created_at,
                run = run_info,
                log = job_log,
                steps = steps,
                diff = diff,
                workflow_config = workflow_config,
                triage = {
                    "label": None,
                    "notes" : "",
                    "heuristic_hint": heuristic_hint(job_log.excerpt)
                }
            )
            print(f"    candidate added for run: {run["id"]}")
            print(f"    ... {len(candidates)}/{max_cases} candidates collected for this fetch", end="\n")
            time.sleep(0.2) # be polite to the API

            candidates.append(c)
            with open(out_path, "a") as f:
                f.write(c.model_dump_json() + "\n")
            per_run += 1

    print(f"\nWrote {len(candidates)} unreviewed candidate to {out_path}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="pandas-dev/pandas")
    parser.add_argument("--max-cases", type=int, default=50)
    parser.add_argument("--max-cases-per-run", type=int, default=2)
    parser.add_argument("--out", default=None)
    parser.add_argument("--since", default=datetime.now() - timedelta(days=90))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN not set - export it or add it to evals/.env")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = (
        Path(args.out) if args.out
        else Path(__file__).parent / "candidates" / f"{args.repo.replace('/','-')}_candidates_{stamp}.jsonl"
    )


    fetch(args.repo, token, args.max_cases, out, args.max_cases_per_run, str(args.since))
        
