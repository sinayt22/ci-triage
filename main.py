import json
import statistics
from schema import EvalCase
from triage import classify

def load(path):
    with open(path) as f:
        return [EvalCase(**json.loads(l)) for l in f] 

def run(cases):
    results = []
    for c in cases:
        pred = classify(c.log_excerpt, c.diff_summary)
        results.append({"id": c.id, "expected": c.label,
                    "predicted": pred, "correct": pred == c.label})
    return results


if __name__ == "__main__":
    cases = load("data/dev.jsonl")
    results = run(cases)
    acc = statistics.mean(r["correct"] for r in results)
    print(f"accuracy: {acc:.1%} ({sum(r['correct'] for r in results)}/{len(results)})")
    for r in results:
        if not r["correct"]:
            print(f" MISS {r['id']}: expected {r['expected']}, got {r['predicted']}")

