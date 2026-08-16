"""
Pulls real, recent CI failures from a GitHub repo's Actions history into
UNREVIEWD candidate records for later hand-labeling.

This does NOT produce ground truth. Every "label" field here is None on
purpose - the label will be diceided later.

"""

import argparse
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
        if text in keywords:
            return label
    return None

def _headers(token:str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-Github-Api-Version": "2022-11-28",
    }

def list_failed_runs(repo:str, token:str, max_runs:int):
    runs = []
    page = 1
    while len(runs) < max_runs:
        response = requests.get(
            f"{API}/repos/{repo}/actions/runs",
            headers=_headers(token),
            params={"status": "failure", "per_page": 100, "page": page}
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

def list_failed_jobs(repo: str, run_id:int, token: str):
    response = requests.get(
        f"{API}/repose/{repo}/actions/runs/{run_id}/jobs",
        headers=_headers(token))
    if response.status_code != 200:
        return []

    jobs = response.json().get("jobs", [])
    return [j for j in jobs if j.get("conclusion") == "failure"]

def get_job_log_excerpt(repo:str, job_id:int, token:str, max_lines:int = 150) -> str | None:
    response = requests.get(f"{API}/repos/{repo}/actions/jobs/{job_id}/logs",
                            headers=_headers(token))
    if response.status_code != 200:
        return None

    lines = [TIMESTAMP_PREFIX.sub("", line) for line in response.text.splitlines()]
    tail = lines[-max_lines:]
    return "\n".join(tail).strip()

def get_diff_summary(repo:str, run:dict, token:str, max_files:int = 5) -> str | None:
    prs = run.get("pull_requests") or []
    if prs:
        pr_number = prs[0]["number"]
        response = requests.get(f"{API}/repos/{repo}/pulls/{pr_number}/files",
                                headers=_headers(token))
    else:
        sha = run.get("head_sha")
        if not sha:
            return None
        response = requests.get(f"{API}/repos/{repo}/commits/{sha}",
                                headers=_headers(token))

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
    
        
