"""
WEB UI for reviewing unlabled CI-failure candidates.

Reads a candidates JSONL, appends EvalCase rows to data/labeled.jsonl, 
and is resumable - already-labeled ids are reported so the UI can skip ahead.


Usage:
    uv run uvicorn labeling.server:app --reload \
    -- port 8000


Then open http://localhost:8000

Config:
    CI_TRIAGE_CANDIATES  required - path to the candidates.jsonl from sourcing
    CI_TRIAGE_OUT optional - output dataset(default: data/labeled.jsonl)

Candidates and labels are loaded once at import and held in memory
"""

import os
from pathlib import Path
from typing import get_args

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from labeling import store
from schema import Label

LABELS = list(get_args(Label))
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _candidates_path() -> Path:
    raw = os.environ.get("CI_TRIAGE_CANDIDATES")
    if not raw:
        raise RuntimeError(
            "CI_TRIAGE_CANDIDATES is not set - point it at the candidates.jsonl "
            "file from sourcing/candidates"
        )

    path = Path(raw)
    if not path.is_file():
        raise RuntimeError(f"CI_TRIAGE_CANDIDATES does not exists: {path}")
    return path


CANDIDATES_PATH = _candidates_path()
OUT_PATH = Path(os.environ.get("CI_TRIAGE_OUT", store.DEFAULT_OUT_PATH))

CANDIDATES = store.load_candidates(CANDIDATES_PATH)
LABELED = store.LabelStore(OUT_PATH)

app = FastAPI(title="CI Triage Labeler")


class LabelRequest(BaseModel):
    id: str
    label: Label
    notes: str = ""


class LabelResponse(BaseModel):
    ok: bool
    labeled_count: int


@app.get("/api/candidates")
def list_candidates() -> list[dict]:
    return [c.model_dump() for c in CANDIDATES.values()]


@app.get("/api/labels")
def list_labels() -> list[str]:
    return LABELS


@app.get("/api/labeled")
def list_labeled() -> dict[str, dict]:
    return {
        id_: {"label": case.label, "notes": case.notes}
        for id_, case in LABELED.cases.items()
    }


@app.post("/api/label", response_model=LabelResponse)
def save_label(req: LabelRequest) -> LabelResponse:
    candidate = CANDIDATES.get(req.id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"unknown candidate id: {req.id}")
    if req.label == "unknown" and not req.notes.strip():
        raise HTTPException(
            status_code=400, detail="notes are required whenlabeling 'unknown'"
        )
    count = LABELED.put(candidate, req.label, req.notes)
    return LabelResponse(ok=True, labeled_count=count)


@app.delete("/api/label/{candidate_id}", response_model=LabelResponse)
def remove_label(candidate_id: str) -> LabelResponse:
    labeled_count = LABELED.delete(candidate_id=candidate_id)
    return LabelResponse(ok=True, labeled_count=labeled_count)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
