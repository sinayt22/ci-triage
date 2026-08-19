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

import requests
from dotenv import load_dotenv

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
        page += 1
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

def get_job_log_excerpt(repo:str, job_id:int, session: requests.Session, max_lines:int = 150) -> str | None:
    response = session.get(f"{API}/repos/{repo}/actions/jobs/{job_id}/logs")
    if response.status_code != 200:
        return None

    lines = [TIMESTAMP_PREFIX.sub("", line) for line in response.text.splitlines()]
    tail = lines[-max_lines:]
    return "\n".join(tail).strip()

def get_diff_summary(repo:str, run:dict, session:requests.Session, max_files:int = 5) -> str | None:
    prs = run.get("pull_requests") or []
    if prs:
        pr_number = prs[0]["number"]
        response = session.get(f"{API}/repos/{repo}/pulls/{pr_number}/files")
    else:
        sha = run.get("head_sha")
        if not sha:
            return None
        response = session.get(f"{API}/repos/{repo}/commits/{sha}")

    if response.status_code != 200:
        return None

    files = response.json() if prs else response.json().get("files", [])
    if not files:
        return None

    parts = [f"{f['filename']} +{f.get('additions', 0)}/-{f.get('deletions', 0)}" for f in files]
    summary = f"{len(files)} files(s) changed: " + ", ".join(parts)
    if len(files) > max_files:
        summary += f", + {len(files) - max_files} more"
    return summary

def fetch(repo: str, token:str, max_cases:int, out_path:Path, since: str = None):
    session = make_session(token)

    print(f"Listing failed runs for {repo} ... ")
    runs = list_failed_runs(repo, session, max_cases * 2, since)
    print(f"    Found {len(runs)} failed run(s) to inspect")

    candidates = []
    
    for run in runs:
        if len(candidates) >= max_cases:
            break

        diff_summary = get_diff_summary(repo, run, session)

        failed_jobs = list_failed_jobs(repo, run["id"], session)
        if not failed_jobs:
            continue

        for job in failed_jobs:
            if len(candidates) >= max_cases:
                break
            excerpt = get_job_log_excerpt(repo, job["id"], session)
            if not excerpt:
                continue

            candidates.append({
                "id": f"{repo.replace('/', '-')}-run{run["id"]}-job{job["id"]}",
                "repo": repo,
                "log_excerpt": excerpt,
                "diff_summary": diff_summary,
                "label": None,
                "heuristic_hint": heuristic_hint(excerpt),
                "notes": "",
                "source_url": run.get("html_url"),
                "job_name": job.get("name"),
                "created_at": run.get("created_at")
            })
            print(f"    candidate added for run: {run["id"]}")
            print(f"    ... {len(candidates)}/{max_cases} candidates collected", end="\r")
            time.sleep(0.2) # be polite to the API


    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")

    print(f"\nWrote {len(candidates)} unreviewed candidate to {out_path}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="pandas-dev/pandas")
    parser.add_argument("--max-cases", type=int, default=50)
    parser.add_argument("--out", default=None)
    parser.add_argument("--since", default=datetime.now() - timedelta(days=90))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN not set - export it or add it to evals/.env")

    out = (
        Path(args.out) if args.out
        else Path(__file__).parent / "candidates" / f"{args.repo.replace('/','-')}_candidates.jsonl"
    )
    fetch(args.repo, token, args.max_cases, out, str(args.since))
        
