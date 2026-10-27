# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
Unit tests for the context Script 1 sends with each field (Day 6, H3 and H4):
neighbour fields on the same object, further metadata (label, help text,
length, decimal places) and the optional org context file.

Run with plain Python (no pytest needed):
  python tests/test_context.py
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec    = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
script1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script1)


def field(name: str, desc: str = "", obj: str = "Contact", ftype: str = "Text", status: str = "FLAGGED") -> dict:
    return {"object": obj, "field_api_name": name, "field_type": ftype, "description": desc,
            "picklist_values": [], "formula": None, "related_object": None,
            "classifier_status": status, "rule_triggered": "R1"}


def contact_fields() -> list[dict]:
    fs = [field("Gear_Size_Notes__c"),
          field("Clothing_Size__c", "Clothing size of this contact. Values: XS, S, M, L, XL.", ftype="Picklist"),
          field("Shoe_Size_EU__c", "Shoe size in EU sizing.", ftype="Number"),
          field("Certification_Level__c", "Highest certification held.", ftype="Picklist"),
          field("Certification_Expiry__c", "", ftype="Date"),
          field("Account_Billing_Proxy__c", "Copied from Gear_Size_Notes__c on save."),
          field("Id", "Record id.", ftype="Id", status="SKIPPED")]
    # Pad the object so that "Notes" is a common word (in more than a fifth of the names)
    fs += [field(f"Topic_{i}_Notes__c", "Notes.") for i in range(8)]
    return fs


def names(f: dict) -> list[str]:
    return [n["field_api_name"] for n in f.get("neighbour_fields", [])]


def test_name_words() -> bool:
    return (script1._name_words("Shoe_Size_EU__c") == {"shoe", "size", "eu"}
            and script1._name_words("OwnerId") == {"owner"}
            and script1._name_words("LastModifiedById") == {"last", "modified"})


def test_shared_word_neighbours() -> bool:
    fs = contact_fields()
    script1.add_neighbour_fields(fs, 5)
    gear = names(fs[0])
    return "Clothing_Size__c" in gear and "Shoe_Size_EU__c" in gear


def test_common_word_ignored() -> bool:
    fs = contact_fields()
    script1.add_neighbour_fields(fs, 5)
    return not any(n.startswith("Topic_") for n in names(fs[0]))


def test_mention_counts() -> bool:
    fs = contact_fields()
    script1.add_neighbour_fields(fs, 5)
    return "Account_Billing_Proxy__c" in names(fs[0])


def test_certification_pair() -> bool:
    fs = contact_fields()
    script1.add_neighbour_fields(fs, 5)
    return names(fs[4]) == ["Certification_Level__c"]


def test_max_and_off() -> bool:
    fs = contact_fields()
    script1.add_neighbour_fields(fs, 1)
    one = len(fs[0]["neighbour_fields"]) == 1
    fs = contact_fields()
    script1.add_neighbour_fields(fs, 0)
    return one and not any("neighbour_fields" in f for f in fs)


def test_skipped_and_other_objects() -> bool:
    fs = contact_fields() + [field("Clothing_Size_Policy__c", "Policy.", obj="Account")]
    script1.add_neighbour_fields(fs, 5)
    return "neighbour_fields" not in fs[6] and "Clothing_Size_Policy__c" not in names(fs[0])


def test_long_description_cut() -> bool:
    fs = [field("Size_A__c"), field("Size_B__c", "word " * 60)]
    script1.add_neighbour_fields(fs, 5)
    d = fs[0]["neighbour_fields"][0]["description"]
    return len(d) <= script1.NEIGHBOUR_DESC_CHARS + 2 and d.endswith("…")


def test_payload_extras() -> bool:
    f = {**field("Tier__c"), "help_text": "Pick the tier.", "length": 40, "label": "",
         "neighbour_fields": [{"field_api_name": "Tier_Since__c", "field_type": "Date", "description": ""}]}
    entry = script1.build_llm_payload({"fields": [f]}, {})[0]
    return (entry["help_text"] == "Pick the tier." and entry["length"] == 40
            and "label" not in entry and entry["neighbour_fields"][0]["field_api_name"] == "Tier_Since__c")


def test_payload_plain() -> bool:
    entry = script1.build_llm_payload({"fields": [field("Tier__c")]}, {})[0]
    return set(entry) == {"field_api_name", "field_type", "description", "picklist_values",
                          "formula", "related_object", "rule_triggered"}


def test_dedup_respects_context() -> bool:
    a = {**field("A__c", "Same text.", obj="Account"), "neighbour_fields": [{"field_api_name": "X__c"}]}
    b = {**field("B__c", "Same text.", obj="Contact"), "neighbour_fields": [{"field_api_name": "Y__c"}]}
    c = field("C__c", "Same text.", obj="Case")
    d = field("D__c", "Same text.", obj="Case")
    unique, dups = script1.sort_and_deduplicate([a, b, c, d])
    return len(unique) == 3 and len(dups) == 1


def test_org_context_in_system_message() -> bool:
    prompts = {"system": "SYSTEM", "examples_parsed": [], "org_context": "Grades A-D: A is best.\n"}
    with_ctx = script1._build_system_message("prompt_a", prompts)
    without  = script1._build_system_message("prompt_a", {**prompts, "org_context": ""})
    return ("## Org Context" in with_ctx and with_ctx.endswith("Grades A-D: A is best.")
            and "## Org Context" not in without)


def test_org_context_loaded() -> bool:
    none = script1.load_prompts({"options": {}})["org_context"] == ""
    path = ROOT / "data" / "org_context_synthetic.md"
    if not path.exists():
        return none
    loaded = script1.load_prompts({"options": {"org_context_file": "data/org_context_synthetic.md"}})
    return none and loaded["org_context"] == path.read_text(encoding="utf-8")


TESTS = [test_name_words, test_shared_word_neighbours, test_common_word_ignored, test_mention_counts,
         test_certification_pair, test_max_and_off, test_skipped_and_other_objects, test_long_description_cut,
         test_payload_extras, test_payload_plain, test_dedup_respects_context,
         test_org_context_in_system_message, test_org_context_loaded]


def main() -> int:
    failures = 0
    for t in TESTS:
        ok = t()
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {t.__name__}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
