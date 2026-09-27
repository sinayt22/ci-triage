"""
Read/Write layer for the labeling dataset.

Owns the on-disk format of candidates and labeled output so that UI clients
agree about it.

"""


import json
from pathlib import Path

from schema import Candidate, EvalCase, Label, candidate_to_eval_case


ROOT = (Path(__file__).resolve().parent.parent)
DEFAULT_OUT_PATH = ROOT / "data" / "labeled.jsonl"

class LabelStore:
    """
    In-memory labeled set, mirrored to a JSONL file on every change.
    """

    def __init__(self, out_path: Path):
        self.out_path = out_path
        self.cases: dict[str, EvalCase] = load_labeled(out_path)

    def put(self, candidate: Candidate, label: Label, notes: str= "") -> int:
        self.cases[candidate.id] = candidate_to_eval_case(candidate,
                                                          label,
                                                          notes)
        self._flush()
        return len(self.cases)

    def delete(self, candidate_id: str) -> int:
        self.cases.pop(candidate_id, None)
        self._flush()
        return len(self.cases)
    
    def _flush(self) -> None:
        save_labeled(self.cases, self.out_path)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]

def load_candidates(path: Path) -> dict[str, Candidate]:
    """Parse and validate every candidate, keyed by id.
    
    Invalid rows are skipped with warning, rather than aborting.
    """

    out: dict[str, Candidate] = {}
    for row in load_jsonl(path):
        try:
            out[row["id"]] = Candidate(**row)
        except Exception as e:
            print(f"! skipping invalid candidate {row.get('id')}: {e}")
    return out

def load_labeled(out_path: Path) -> dict[str, EvalCase]:
    return {row["id"]: EvalCase(**row) for row in load_jsonl(out_path)}

def save_labeled(cases: dict[str, EvalCase], out_path: Path) -> None:

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".jsonl.tmp")

    with open(tmp, "w") as f:
        for case in cases.values():
            f.write(case.model_dump_json() + "\n")

    tmp.replace(out_path)






