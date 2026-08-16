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

