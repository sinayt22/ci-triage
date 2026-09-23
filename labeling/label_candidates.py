"""
Interactive CLI for reviewing unlabeled CI-failure candidates and turning them into real,
hand-labeled dataset entries.

This is the human in the loop step - candidates arrive with label=None and an unverified
heuristic hint. This tool is where a human actually reads each one and decided, per TAXONOMY.md's
rules

Usage:
    python3 labeling/label_candidates.py \
    --candidates sourcing/candidates/<lib_name>_candidates.jsonl \
    --out-path data/labeled.jsonl
    --limit 20

Resumable: on startup, any id already present in --out is skipped, so you can restart
without re-reviewing or duplicating.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import get_args



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import schema
from schema import Candidate, EvalCase, Label, candidate_to_eval_case

LABELS = list(get_args(Label))

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def already_reviewed_ids(out_path: Path) -> set:
    return {row["id"] for row in load_jsonl(out_path)}

def print_candidate(c: Candidate, index: int, total: int) -> None:
    print("\n" + "=" * 78)
    print(f"[{index}]/{total}] {c.id}")
    print(f"repo:   {c.repo}")
    print(f"source: {c.run.run_url}")
    print("-" * 78)
    print(f"FAILED STEP: {c.steps.failed_step_name}")
    print("-" * 78)
    print(f"EVENT: {c.run.event}")
    print("-" * 78)
    print(f"RUN ATTEMPT: {c.run.run_attempt}")
    print("-" * 78)
    workflow_config = c.workflow_config if len(c.workflow_config) < 1024 else f"{c.workflow_config} ...[[TRUNCATED]] "
    print(f"WORKFLOW CONFIG: {c.workflow_config}")
    print("-" * 78)
    print("LOG EXCERPT:")
    print(c.log.excerpt or "(not provided)")
    print("-" * 78)
    print("DIFF SUMMARY:")
    print(c.diff.summary or "(not provided )")
    print("-" * 78)

    hint = c.triage.heuristic_hint
    if hint:
        print(f"heuristic_hint (Unverified): {hint}")
    print("=" * 78)

def prompt_label() -> str | None:
    print("\nLabel:")
    for i, label in enumerate(LABELS, start=1):
        print(f"    {i}. {label}")
    print("    s.skip (revisit later)")
    print("    q.quit (progress already saved)")

    while True:
        choice = input("> ").strip().lower()
        if choice == "q":
            return "QUIT"
        if choice == "s":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(LABELS):
            return LABELS[int(choice) - 1]
        print(f"    invalid input - enter 1-{len(LABELS)}, 's', or 'q'")

def prompt_notes(label: str) -> str:
    required = label == 'unknown'
    prompt = (
        "Notes (Required - explain your reasoning): "
        if required else
        "Notes (optional, Enter to skip): "
    )
    while True:
        notes = input(prompt).strip()
        if notes or not required:
            return notes
        print(" notes are required, explaining what you considered")

def label_candidates(candidates_path: Path, out_path: Path, limit: int | None) -> None:
    candidates = load_jsonl(candidates_path)
    done = already_reviewed_ids(out_path)
    todo = [c for c in candidates if c["id"] not in done]

    print(f"{len(candidates)} candidates total, {len(done)} already reviewd, {len(todo)} remaining.")
    if limit:
        todo = todo[:limit]
        print(f"Limiting this session to {len(todo)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    saved_count = 0

    for i, c in enumerate(todo, start=1):
        try:
            candidate = schema.Candidate(**c)
        except Exception as e:
            print(f" ! record failed schema validation, NOT saved: {e}")
            continue

        print_candidate(candidate, i, len(todo))
        label = prompt_label()

        if label == "QUIT":
            print(f"\nStopped. {saved_count} labeled, {i - 1 - saved_count} skipped, "
                  f"{len(todo) - i + 1} remaining - resume anytime with the same command.")
            return
        if label is None:
            print(" skipped.")
            continue
        notes = prompt_notes(label)


        record = candidate_to_eval_case(c=candidate, label=label, notes=notes)

        with open(out_path, "a") as f:
            f.write(record.model_dump_json() + "\n")
        saved_count += 1
        print(f" -> saved as {label}")

    print(f"\nDone. {saved_count}/{len(todo)} labeled this batch.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="Path to a candidates.jsonl file from sourcing")
    parser.add_argument("--out-path", default=None, help="Output labeled dataset file (default: data/labeled.jsonl)")
    parser.add_argument("--limit", type=int, default=None, help="Review at most N candidates this session")
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    default_out_path = Path(__file__).resolve().parent.parent / "data" / "labeled.jsonl"
    out_path = Path(args.out_path) if args.out_path else default_out_path
    label_candidates(candidates_path, out_path, args.limit)


