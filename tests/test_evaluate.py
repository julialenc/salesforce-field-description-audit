# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
Unit tests for scripts/evaluate_suggestions.py (the automatic suggestion check).

Run with plain Python (no pytest needed):
  python tests/test_evaluate.py
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("evaluate", ROOT / "scripts" / "evaluate_suggestions.py")
ev   = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

GOOD = ("Date the customer signed the current supply agreement, entered by the "
        "account manager from the signed contract. Starts the renewal reminder workflow.")
LONG = ("Free-text field storing negotiation notes for this opportunity, including discount "
        "requests submitted, justification provided, approval decisions at each level, "
        "counter-proposals from the prospect, and final agreed terms.")


def field(rule, desc="Old text that the classifier flagged.", ftype="Date", picklist=None):
    status = {"R1": "FLAGGED", "R2": "FLAGGED", "R3": "FLAGGED", "R4": "FLAGGED", "R5": "FLAGGED",
              "R6": "UNCERTAIN", "R7": "UNCERTAIN", "R8": "UNCERTAIN", "R9": "UNCERTAIN"}.get(rule, "REVIEWED")
    return {"object": "Account", "field_api_name": "Test__c", "field_type": ftype, "description": desc,
            "picklist_values": picklist or [], "classifier_status": status, "rule_triggered": rule}


def answer(text, action="rewrite"):
    return {"action": action, "suggested_description": text}


# (name, field, answer, expected failed checks, expected notes)
CASES = [
    ("good rewrite passes",          field("R1"), answer(GOOD), set(), set()),
    ("too short",                    field("R1"), answer("Signed date."), {"length", "reclassify"}, set()),
    ("over 255 characters",          field("R1"), answer(GOOD + " " + GOOD), {"length"}, set()),
    ("vague term fails",             field("R1"), answer(GOOD + " Kept for reporting purposes where relevant."), {"vague"}, set()),
    ("'used by' is a note only",     field("R1"), answer(GOOD + " Used by the ERP sync."), set(), {"used-phrase"}),
    ("unexplained acronym re-flags", field("R1"), answer(GOOD + " Sent to the QRT engine."), {"reclassify"}, set()),
    ("picklist value missing",       field("R4", ftype="Picklist", picklist=["Gold", "Silver"]),
                                     answer("Commercial tier set by finance at onboarding. Values: Gold."), {"picklist"}, set()),
    ("picklist all values named",    field("R4", ftype="Picklist", picklist=["Gold", "Silver"]),
                                     answer("Commercial tier set by finance at onboarding. Values: Gold, Silver."), set(), set()),
    ("R6 shortened passes",          field("R6", desc=LONG, ftype="Text"),
                                     answer("Negotiation notes for this opportunity: discount requests, approvals and final agreed terms.", "shorten"), set(), set()),
    ("R6 not shorter",               field("R6", desc=LONG, ftype="Text"), answer(LONG, "shorten"), {"shorter", "reclassify", "action"}, set()),
    ("R6 answered with rewrite",     field("R6", desc=LONG, ftype="Text"),
                                     answer("Negotiation notes for this opportunity: discount requests, approvals and final agreed terms."), {"action"}, set()),
    ("R5 retired field is a note",   field("R5", ftype="Text"),
                                     answer("Deprecated segment code from the 2021 ERP migration, replaced by Account_Segment__c."), set(), {"deprecated"}),
    ("R5 still TBD fails",           field("R5", ftype="Text"),
                                     answer("Segment code, purpose TBD with the sales operations team."), {"reclassify"}, set()),
    ("rewrite that changes nothing", field("R9", desc=GOOD), answer(GOOD), {"action"}, set()),
    ("listed assumption is a note",  field("R1", desc=""),
                                     {**answer(GOOD), "assumptions": ["entered by the account manager"]}, set(), {"assumptions"}),
    ("listed missing fact is a note", field("R1", desc=""),
                                     {**answer(GOOD), "missing": ["Which process reads it?"]}, set(), {"missing"}),
    ("empty assumptions, no note",   field("R1", desc=""), {**answer(GOOD), "assumptions": [" "]}, set(), set()),
    ("question in the text fails",   field("R1", desc=""), answer(GOOD + " What does it trigger?"), {"remark"}, set()),
    ("remark about original fails",  field("R1", desc=""), answer(GOOD + " The original named three tiers."), {"remark"}, set()),
    ("'not specified' remark fails", field("R1", desc=""), answer(GOOD + " The unit is not specified."), {"remark"}, set()),
    ("'the original request' passes", field("R1", desc=""), answer(GOOD + " Holds the original request and the approval."), set(), set()),
]


def main() -> int:
    failed = 0
    for name, f, result, want_fail, want_notes in CASES:
        failures, notes = ev.evaluate_one(f, result)
        got_fail, got_notes = set(failures), set(notes)
        ok = got_fail == want_fail and got_notes == want_notes
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}"
              + ("" if ok else f"\n      failures {sorted(got_fail)} (want {sorted(want_fail)}),"
                               f" notes {sorted(got_notes)} (want {sorted(want_notes)})"))
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
