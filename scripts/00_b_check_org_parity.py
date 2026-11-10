# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
00_b_check_org_parity.py

Checks that reading fields from an org gives the pipeline the same input as
the training file: for every custom field of the training set that exists in
the org (seeded with 00_a_seed_demo_org.py), the description, type, picklist
values, formula and lookup target must match, and the classifier must give
the same status and rule. Read-only: nothing is written to the org and no
LLM is called.

  python scripts/00_b_check_org_parity.py [--target-org sfdesc-dev]

Exit code 0 when every seeded field matches.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
DATASET = ROOT / "data" / "sf_metadata_raw_training.json"
OBJECTS = ["Account", "Contact", "Opportunity", "Case"]

spec    = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
script1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script1)
sf_cli  = script1.sf_cli

COMPARED = ("description", "field_type", "picklist_values", "formula", "related_object")


def _norm(value):
    if isinstance(value, list):
        return list(value)
    return " ".join(str(value).split()) if value else ""


def main() -> int:
    args = sys.argv[1:]
    org  = args[args.index("--target-org") + 1] if "--target-org" in args else "sfdesc-dev"

    data    = json.loads(DATASET.read_text(encoding="utf-8"))
    dataset = [f for f in data.get("fields", data) if f["field_api_name"].endswith("__c")]
    in_org  = {f"{f['object']}.{f['field_api_name']}": f for f in sf_cli.read_fields(org, OBJECTS)}

    matched, absent, mismatches = 0, [], []
    for f in dataset:
        key = f"{f['object']}.{f['field_api_name']}"
        o = in_org.get(key)
        if o is None:
            absent.append(key)
            continue
        diffs = [c for c in COMPARED if _norm(f.get(c)) != _norm(o.get(c))]
        a, b = script1._classify_one(dict(f), False), script1._classify_one(dict(o), False)
        if (a["status"], a["rule"]) != (b["status"], b["rule"]):
            diffs.append(f"classified {a['status']}/{a['rule']} from file, {b['status']}/{b['rule']} from org")
        if diffs:
            mismatches.append((key, diffs))
        else:
            matched += 1

    extra = sorted(set(in_org) - {f"{f['object']}.{f['field_api_name']}" for f in dataset})
    print(f"Training custom fields: {len(dataset)} · in org: {len(dataset) - len(absent)} · "
          f"identical input and classification: {matched}")
    for key, diffs in mismatches:
        print(f"  MISMATCH {key}: {'; '.join(diffs)}")
    if absent:
        print(f"Not in the org (not seeded): {', '.join(absent)}")
    if extra:
        print(f"In the org but not in the training set ({len(extra)}): {', '.join(extra)}")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
