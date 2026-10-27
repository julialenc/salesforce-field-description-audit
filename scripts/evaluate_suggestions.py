# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
evaluate_suggestions.py

Automatic quality check for the LLM suggestions written by Script 1.
Every rewritten or shortened description is checked against the
"What Good Output Means" criteria in wiki 03:

  reclassify   the suggestion, run back through the classifier, comes out REVIEWED
  length       30-255 characters
  vague        no vague terms from the wiki 03 rejection list ("relevant",
               "various", "for reporting", ...)
  remark       no question and no remark to the Admin ("The original named …",
               "… is not specified"): the text is what gets written to Salesforce
  picklist     every picklist value is named (Picklist / MultiselectPicklist)
  shorter      R6 only: shorter than the original and at most 200 characters
  action       the action the prompt asks for (A: rewrite, B/R6: shorten,
               B/R7-R9: rewrite); a rewrite must change the text

"keep" answers (Prompt B and C) are not checked: the text is the original.
They are counted, so the Prompt C rewrite rate is visible next to the pass rate.

Two findings are counted as notes, not failures:
  used-phrase  "used to / used for / used by". The system prompt allows them when
               specific content follows ("Used by the ERP sync to set the tax
               code"), which a keyword check can't judge
  deprecated   an R5 rewrite that states the field is deprecated, as Prompt A
               asks for genuinely retired fields. It re-flags as R5 by design
  assumptions  the LLM listed claims it could not confirm from the input
               (the "assumptions" field, shown as "Unverified" in the review
               file). Not wrong by itself, but the Admin must check them
  missing      the LLM listed facts the input does not give ("missing", shown
               as "Missing" in the review file). The Admin adds them

Usage:
  python scripts/evaluate_suggestions.py
      Reads data/sf_classified.json and data/llm_response.json.
  python scripts/evaluate_suggestions.py data/llm_response_groq_gpt-oss-120b_20261024.json
      Evaluates another saved LLM response file against data/sf_classified.json.
  Add --failures to list every failed suggestion with its reasons.
  Add --assumptions to list every suggestion with assumptions or missing
  facts, grouped by prompt and rule, to look for patterns in what the model
  guesses and what it cannot know.

Exit code is 0 (this is a report, not a gate).
"""

import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent
CLASSIFIED = ROOT / "data" / "sf_classified.json"
RESPONSE   = ROOT / "data" / "llm_response.json"

spec    = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
script1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script1)

MIN_LEN, MAX_LEN, R6_MAX_LEN = 30, 255, 200

# Wiki 03 rejection list, plus the system prompt's "for tracking" group.
# Placeholder terms (TBD, N/A, see above, ask, deprecated) are left to the
# reclassify check, which runs them through R5 with whole-word matching.
VAGUE_TERMS = [
    "relevant", "applicable", "various", "related to",
    "for tracking", "for reporting", "for reference", "internal use",
]
USAGE_PHRASES = ["used for", "used by", "used to"]

# Remarks about the input or about what is unknown, which belong in "missing"
REMARK_PHRASES = [
    "original description", "the input", "not specified", "unspecified",
    "is unknown", "are unknown", "not known", "not documented", "not stated", "not given",
    "not provided", "not defined in",
]
# "The original named / says / only …", but not "the original request" (a fact about the record)
REMARK_ORIGINAL = re.compile(r"\bthe original (?:\w+ed|says|said|only|text|field)\b", re.IGNORECASE)

# R5 tokens that mean "not written yet", as opposed to "retired"
UNFINISHED_TOKENS = [
    "tbd", "to be defined", "to be confirmed", "to be agreed", "todo", "to do",
    "fixme", "n/a", "see above", "see below", "ask", "check with",
]

CHECKS = ["reclassify", "length", "vague", "remark", "picklist", "shorter", "action"]
NOTES  = ["used-phrase", "deprecated", "assumptions", "missing"]


def load_fields(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fields", data) if isinstance(data, dict) else data


def load_results(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", []) if isinstance(data, dict) else data
    return {f"{r.get('object')}.{r.get('field_api_name')}": r for r in results}


def prompt_for(f: dict) -> str | None:
    return {"FLAGGED": "A", "UNCERTAIN": "B", "REVIEWED": "C"}.get(f.get("classifier_status"))


def find_terms(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [t for t in terms
            if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", lower)]


def missing_picklist_values(text: str, picklist: list) -> list[str]:
    lower = text.lower()
    return [v for v in picklist
            if not re.search(r"(?<![a-z0-9])" + re.escape(v.lower()) + r"(?![a-z0-9])", lower)]


def evaluate_one(f: dict, result: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Return ({check: reason} for every failed check, {note: reason}). No failures means pass."""
    suggestion = (result.get("suggested_description") or "").strip()
    original   = (f.get("description") or "").strip()
    action     = result.get("action")
    rule       = f.get("rule_triggered")
    failures, notes = {}, {}

    reclassified = script1._classify_one({**f, "description": suggestion}, include_standard=True)
    if (rule == "R5" and reclassified["rule"] == "R5"
            and not find_terms(suggestion, UNFINISHED_TOKENS)):
        notes["deprecated"] = "states the field is retired"
    elif reclassified["status"] != "REVIEWED":
        failures["reclassify"] = f"{reclassified['status']}/{reclassified['rule']}"

    if not MIN_LEN <= len(suggestion) <= MAX_LEN:
        failures["length"] = f"{len(suggestion)} chars"

    found = find_terms(suggestion, VAGUE_TERMS)
    if found:
        failures["vague"] = ", ".join(found)
    found = find_terms(suggestion, USAGE_PHRASES)
    if found:
        notes["used-phrase"] = ", ".join(found)
    found = (find_terms(suggestion, REMARK_PHRASES) + REMARK_ORIGINAL.findall(suggestion)
             + (["?"] if "?" in suggestion else []))
    if found:
        failures["remark"] = ", ".join(found)

    if f.get("field_type") in ("Picklist", "MultiselectPicklist") and f.get("picklist_values"):
        missing = missing_picklist_values(suggestion, f["picklist_values"])
        if missing:
            failures["picklist"] = "missing " + ", ".join(missing)

    assumed = [str(a).strip() for a in (result.get("assumptions") or []) if str(a).strip()]
    if assumed:
        notes["assumptions"] = "; ".join(assumed)
    missing = [str(m).strip() for m in (result.get("missing") or []) if str(m).strip()]
    if missing:
        notes["missing"] = "; ".join(missing)

    if rule == "R6" and not (len(suggestion) < len(original) and len(suggestion) <= R6_MAX_LEN):
        failures["shorter"] = f"{len(original)} -> {len(suggestion)} chars"

    expected = "shorten" if rule == "R6" else "rewrite"
    if action != expected:
        failures["action"] = f"{action}, expected {expected}"
    elif suggestion == original:
        failures["action"] = "text unchanged"

    return failures, notes


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.1%})" if d else "0/0"


def main() -> int:
    sys.stdout.reconfigure(errors="replace")   # LLM text may hold characters the Windows console can't show
    args          = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_failures = "--failures" in sys.argv
    show_assumed  = "--assumptions" in sys.argv
    response_path = Path(args[0]) if args else RESPONSE
    if not response_path.is_absolute():
        response_path = ROOT / response_path
    for p in (CLASSIFIED, response_path):
        if not p.exists():
            print(f"File not found: {p}. Run Script 1 first.")
            return 2

    fields  = load_fields(CLASSIFIED)
    results = load_results(response_path)

    sent, evaluated, passed = defaultdict(int), defaultdict(int), defaultdict(int)
    keeps, errors, missing  = defaultdict(int), defaultdict(int), defaultdict(int)
    check_fails             = defaultdict(lambda: defaultdict(int))
    note_counts             = defaultdict(lambda: defaultdict(int))
    failed_rows             = []
    assumed_rows            = []

    for f in fields:
        prompt = prompt_for(f)
        if prompt is None:
            continue
        group  = f"{prompt} {f.get('rule_triggered') or '-'}"
        key    = f"{f.get('object')}.{f.get('field_api_name')}"
        result = results.get(key)
        sent[group] += 1
        if result is None:
            missing[group] += 1
            continue
        if result.get("llm_error") or result.get("action") == "llm_error":
            errors[group] += 1
            continue
        if result.get("action") == "keep" and prompt != "A" and f.get("rule_triggered") != "R6":
            keeps[group] += 1
            continue
        evaluated[group] += 1
        failures, notes = evaluate_one(f, result)
        for note in notes:
            note_counts[prompt][note] += 1
        if "assumptions" in notes or "missing" in notes:
            assumed_rows.append((group, key, notes.get("assumptions", ""), notes.get("missing", ""),
                                 result.get("suggested_description", "")))
        if failures:
            for check in failures:
                check_fails[prompt][check] += 1
            failed_rows.append((group, key, failures, result.get("suggested_description", "")))
        else:
            passed[group] += 1

    print(f"Suggestions: {response_path.name}  (classification: {CLASSIFIED.name})\n")
    print(f"{'Prompt / rule':<15}{'Sent':>6}{'Keep':>6}{'Error':>7}{'Checked':>9}   Pass")
    groups = sorted(sent, key=lambda g: (g[0], g[2:] == "-", g))
    for prompt in ("A", "B", "C"):
        rows = [g for g in groups if g[0] == prompt]
        for g in rows:
            print(f"  {g:<13}{sent[g]:>6}{keeps[g]:>6}{errors[g] + missing[g]:>7}{evaluated[g]:>9}   {pct(passed[g], evaluated[g])}")
        tot = lambda d: sum(d[g] for g in rows)
        print(f"{'Prompt ' + prompt:<15}{tot(sent):>6}{tot(keeps):>6}{tot(errors) + tot(missing):>7}"
              f"{tot(evaluated):>9}   {pct(tot(passed), tot(evaluated))}")
        if check_fails[prompt]:
            print("    failed checks: " + ", ".join(f"{c} {check_fails[prompt][c]}"
                                                    for c in CHECKS if check_fails[prompt][c]))
        if note_counts[prompt]:
            print("    notes (not failures): " + ", ".join(f"{n} {note_counts[prompt][n]}"
                                                         for n in NOTES if note_counts[prompt][n]))
        print()

    all_eval, all_pass = sum(evaluated.values()), sum(passed.values())
    print(f"All prompts: {pct(all_pass, all_eval)} of checked suggestions pass")

    if show_failures and failed_rows:
        print("\nFailed suggestions:")
        for group, key, failures, text in failed_rows:
            reasons = "; ".join(f"{c}: {r}" for c, r in failures.items())
            print(f"  [{group}] {key}: {reasons}\n      {text}")

    if show_assumed and assumed_rows:
        print(f"\nSuggestions with assumptions or missing facts ({len(assumed_rows)} of {all_eval} checked):")
        for group, key, assumed, missing, text in sorted(assumed_rows):
            print(f"  [{group}] {key}\n      {text}"
                  + (f"\n      assumed: {assumed}" if assumed else "")
                  + (f"\n      missing: {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
