"""
WEB UI for reviewing unlabled CI-failure candidates.

Reads a candidates JSONL, appends EvalCase rows to data/labeled.jsonl, 
and is resumable - already-labeled ids are reported so the UI can skip ahead.


Usage:
    uv run uvicorn labeling.server:app --reload \
    -- port 8000

Then open http://localhost:8000
Candidate file is chose with CI_TRIAGE_CANDIATES (see below).
"""

import json
import os
import sys
from pathlib import Path
from typing import get_args

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT)
from schema import Candidate, EvalCase, Label, candidate_to_eval_case

LABELS = list(get_args(Label))
CANDIDATES_PATH = Path(os.environ.get("CI_TRIAGE_CANDIDATES"))
if not CANDIDATES_PATH.exists:
    raise Exception("Candidates path does not exists")

OUT_PATH = Path(os.environ.get("CI_TRIAGE_OUT", ROOT / "data/labeled.jsonl"))

app = FastAPI(title="CI Triage Labeler")