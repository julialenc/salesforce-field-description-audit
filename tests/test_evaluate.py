# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
Unit tests for scripts/03_a_evaluate_suggestions.py (the automatic suggestion check).

Run with plain Python (no pytest needed):
  python tests/test_evaluate.py
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("evaluate", ROOT / "scripts" / "03_a_evaluate_suggestions.py")
ev   = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

GOOD = ("Date the customer signed the current supply agreement, entered by the "
        "account manager from the signed contract. Starts the renewal reminder workflow.")
LONG = ("Free-text field storing negotiation notes for this opportunity, including discount "
        "requests submitted, justification provided, approval decisions at each level, "
        "counter-proposals from the prospect, and final agreed terms.")
RETIRED = "Deprecated. Order code from the old webshop. No longer synced."


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
    ("R5 retired keep, no questions", field("R5", desc=RETIRED, ftype="Text"), answer(RETIRED, "keep"), {"action"}, {"deprecated"}),
    ("R5 TBD kept fails",            field("R5", desc="TBD", ftype="Text"), answer("TBD", "keep"), {"reclassify", "length", "action"}, set()),
    ("Prompt C drops a sentence",    field(None, desc=GOOD), answer(GOOD.split(" Starts")[0]), {"dropped"}, set()),
    ("Prompt C keeps every sentence", field(None, desc=GOOD), answer(GOOD + " Read by the ERP sync."), set(), set()),
    ("Prompt C drops UI instruction", field(None, desc="Select the date from the calendar. " + GOOD), answer(GOOD + " Read by the ERP sync."), set(), set()),
    ("R6 drops list items",          field("R6", desc=LONG, ftype="Text"), answer("Negotiation notes for this opportunity.", "shorten"), {"dropped"}, set()),
]

# (name, field, answer, counted as keep)
KEEP_CASES = [
    ("R5 retired keep with questions", field("R5", desc=RETIRED, ftype="Text"),
                                       {**answer(RETIRED, "keep"), "missing": ["Can it be deleted?"]}, True),
    ("R5 retired keep, empty missing", field("R5", desc=RETIRED, ftype="Text"), {**answer(RETIRED, "keep"), "missing": [" "]}, False),
    ("R5 TBD keep with questions",     field("R5", desc="TBD - confirm with finance.", ftype="Text"),
                                       {**answer("TBD - confirm with finance.", "keep"), "missing": ["Is it in use?"]}, False),
    ("Prompt C keep",                  field(None, desc=GOOD), answer(GOOD, "keep"), True),
    ("R6 keep is checked",             field("R6", desc=LONG, ftype="Text"), answer(LONG, "keep"), False),
    ("Prompt A rewrite",               field("R1"), answer(GOOD), False),
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
    for name, f, result, want in KEEP_CASES:
        ok = ev.counts_as_keep(f, result) == want
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  keep: {name}")
    total = len(CASES) + len(KEEP_CASES)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
