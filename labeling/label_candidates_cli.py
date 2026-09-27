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
from labeling import store
import schema
from schema import Candidate, Label, candidate_to_eval_case

LABELS = list(get_args(Label))
QUIT = "QUIT"


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
    print(f"WORKFLOW CONFIG: {_truncate(c.workflow_config, 1024)}")
    print("-" * 78)
    print("LOG EXCERPT:")
    print(_truncate(c.log.excerpt, 8192) or "(not provided)")
    print("-" * 78)
    print("DIFF SUMMARY:")
    print(c.diff.summary or "(not provided )")
    print("-" * 78)

    hint = c.triage.heuristic_hint
    if hint:
        print(f"heuristic_hint (Unverified): {hint}")
    print("=" * 78)

def _truncate(text: str | None, limit: int) -> str:
    """Cap a text field so the text won't scroll the rest of the screen"""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...[[TRUNCATED {len(text) - limit:,} more chars]]"

def prompt_label(existing_label: str | None) -> str | None:
    print("\nLabel:")
    for i, label in enumerate(LABELS, start=1):
        print(f"    {i}. {label}")
    if existing_label:
        print(f"EXISTING label detected: {existing_label}\n\n")
    print("    s.skip (revisit later)")
    print("    q.quit (progress already saved)")

    while True:
        choice = input("> ").strip().lower()
        if choice == "q":
            return QUIT
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

def label_candidates(candidates_path: Path, 
                     out_path: Path, 
                     limit: int | None,
                     relabel: bool) -> None:
    candidates = store.load_candidates(candidates_path)
    labeled = store.LabelStore(out_path)

    todo = [c 
            for c in candidates.values() 
            if relabel or c.id not in labeled.cases]

    print(f"{len(candidates)} candidates total, {len(labeled.cases)} already reviewd, "
          f"{len(todo)} to review.")


    if relabel:
        print("(--relabel: including already-labeled candidates)")
    
    if limit:
        todo = todo[:limit]
        print(f"Limiting this session to {len(todo)}")

    saved_count = 0
    skipped_count = 0

    for i, c in enumerate(todo, start=1):
        print_candidate(c, i, len(todo))

        existing = labeled.cases.get(c.id)
        if existing:
            print(f"Already labeled: {existing.id}")
            if existing.notes:
                print(f"  Notes: {existing.notes}")

        label = prompt_label(existing.label if existing else None)

        if label == QUIT:
            print(
                f"\nSTOPPED. {saved_count} labeled, {skipped_count} skipped,"
                f"{len(todo) - i + 1} remaining - resume anytime with same command"
            )
            return

        if label is None:
            print("  skipped.")
            skipped_count += 1
            continue

        notes = prompt_notes(label)
        total = labeled.put(c, label, notes)
        saved_count += 1
        print(f"    -> saved as {label} ({total} labeled in total)")

    print(f"\nDone. {saved_count}/{len(todo)} labeled this batch.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="Path to a candidates.jsonl file from sourcing")
    parser.add_argument("--out-path", default=None, help=f"Output labeled dataset file (default: {store.DEFAULT_OUT_PATH})")
    parser.add_argument("--limit", type=int, default=None, help="Review at most N candidates")
    parser.add_argument("--relabel", type=bool, help="Also revisit candidates that already have a label")
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    if not candidates_path.exists():
        parser.error(f"candidates file not found: {candidates_path}")

    out_path = Path(args.out_path) if args.out_path else store.DEFAULT_OUT_PATH
    label_candidates(candidates_path, out_path, args.limit, args.relabel)


if __name__ == "__main__":
    main()
