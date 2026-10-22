# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
validate_classifier.py

Compares classifier output with the ground truth in each field
(_expected_status / _expected_rule). Prints accuracy per expected rule
and lists every mismatch.

Usage:
  python scripts/validate_classifier.py
      Reads data/sf_classified.json (written by Script 1).
  python scripts/validate_classifier.py data/sf_metadata_raw_training.json
      Classifies a raw dataset directly — no LLM call, no config needed.

Exit code is 1 if there is any mismatch, 0 otherwise.
"""

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent
CLASSIFIED = ROOT / "data" / "sf_classified.json"


def load_fields(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fields", data) if isinstance(data, dict) else data


def classify_raw(fields: list[dict]) -> list[dict]:
    """Run Script 1's classifier on raw fields (include_standard_fields: false, as in config)."""
    spec   = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    for f in fields:
        result = script._classify_one(f, include_standard=False)
        f["classifier_status"] = result["status"]
        f["rule_triggered"]    = result["rule"]
    return fields


def label(status, rule) -> str:
    return f"{status}/{rule}" if rule else str(status)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CLASSIFIED
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"File not found: {path}. Run Script 1 first, or pass a raw dataset path.")
        return 2

    fields = load_fields(path)
    if not fields:
        print(f"{path.name} has no fields. Run Script 1 first, or pass a raw dataset path.")
        return 2
    if "classifier_status" not in fields[0]:
        fields = classify_raw(fields)
    if "_expected_status" not in fields[0]:
        print(f"{path.name} has no _expected_status labels — nothing to compare against.")
        return 2

    totals, correct = defaultdict(int), defaultdict(int)
    mismatches = []
    for f in fields:
        expected = (f.get("_expected_status"), f.get("_expected_rule"))
        actual   = (f.get("classifier_status"), f.get("rule_triggered"))
        group    = label(*expected)
        totals[group] += 1
        if expected == actual:
            correct[group] += 1
        else:
            mismatches.append((f, expected, actual))

    n, n_ok = len(fields), sum(correct.values())
    print(f"Classifier validation — {path.name}")
    print(f"Overall: {n_ok}/{n} match ({100 * n_ok / n:.1f}%)\n")

    print(f"{'Expected':<16}{'Match':>8}{'Total':>8}{'Accuracy':>10}")
    order = {"FLAGGED": 0, "UNCERTAIN": 1, "REVIEWED": 2, "SKIPPED": 3}
    for group in sorted(totals, key=lambda g: (order.get(g.split("/")[0], 9), g)):
        print(f"{group:<16}{correct[group]:>8}{totals[group]:>8}{100 * correct[group] / totals[group]:>9.1f}%")

    print(f"\nMismatches: {len(mismatches)}")
    for f, expected, actual in mismatches:
        print(f"\n- {f.get('object')}.{f.get('field_api_name')} ({f.get('field_type')})")
        print(f"  expected {label(*expected)}, got {label(*actual)}")
        print(f"  description: {(f.get('description') or '')!r}")

    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
