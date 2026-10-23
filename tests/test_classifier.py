# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
Unit tests for the rule-based classifier in Script 1.

Run with plain Python (no pytest needed):
  python tests/test_classifier.py

Each case names the rule it covers. Cases marked "fix" guard the known
classifier fixes that must not be reverted.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec    = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
script1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script1)

GOOD = ("Date the customer signed the current supply agreement, entered by the "
        "account manager from the signed contract and used to schedule renewals.")

# (name, field_api_name, field_type, description, picklist_values, expected_status, expected_rule)
CASES = [
    ("SKIPPED system field",         "CreatedDate",  "DateTime", "Created date.", [], "SKIPPED", None),
    ("SKIPPED standard Id",          "AccountId__x", "Id",       GOOD, [], "SKIPPED", None),
    ("R1 empty description",         "Region__c",    "Text",     "", [], "FLAGGED", "R1"),
    ("R1 whitespace only",           "Region__c",    "Text",     "   ", [], "FLAGGED", "R1"),
    ("R2 too short",                 "Region__c",    "Text",     "The region.", [], "FLAGGED", "R2"),
    ("R2 echo of field name",        "Customer_Lifetime_Value__c", "Currency",
                                     "Stores the customer lifetime value for this field.", [], "FLAGGED", "R2"),
    ("R3 checkbox asks for text",    "Is_Active__c", "Checkbox", "Enter the reason the account was activated by the team.", [], "FLAGGED", "R3"),
    ("R3 number described as dropdown", "Seats__c",  "Number",   "Number of seats, choose from the list provided by sales ops.", [], "FLAGGED", "R3"),
    ("R4 picklist values missing",   "Tier__c",      "Picklist", "Commercial tier assigned to the account by the finance team.", ["Gold", "Silver"], "FLAGGED", "R4"),
    ("R4 not fired when a value is named", "Tier__c", "Picklist", "Commercial tier assigned by finance: Gold for top accounts, Silver otherwise.", ["Gold", "Silver"], "REVIEWED", None),
    ("R5 placeholder",               "Region__c",    "Text",     "Purpose to be defined with the regional sales operations team.", [], "FLAGGED", "R5"),
    ("R5 deprecated",                "Old_Code__c",  "Text",     "Deprecated code from the previous ERP migration, kept for history.", [], "FLAGGED", "R5"),
    ("R6 long and lists its contents", "Notes__c",   "Text",     "Free-text field storing negotiation notes for this opportunity, including discount requests submitted, justification provided, approval decisions at each level, counter-proposals from the prospect, and final agreed terms.", [], "UNCERTAIN", "R6"),
    ("R6 not fired on length alone", "Notes__c",     "Text",     GOOD + " " + GOOD, [], "REVIEWED", None),
    ("R6 not fired on a short list", "Notes__c",     "Text",     "Notes on the partnership agreement, including terms, amendments, exceptions and renewals.", [], "REVIEWED", None),
    ("R7 unexplained acronym",       "Score__c",     "Number",   "Score from the QRT model refreshed nightly for every account record.", [], "UNCERTAIN", "R7"),
    ("R7 acronym expanded inline",   "Score__c",     "Number",   "Score from the QRT (quarterly risk tool) model, refreshed nightly.", [], "REVIEWED", None),
    ("R8 single email holds a list", "Billing_Email__c", "Email", "All addresses that should receive invoices for this account record.", [], "UNCERTAIN", "R8"),
    ("R9 written for end users",     "Region__c",    "Text",     "Make sure to update the sales region whenever the account moves office.", [], "UNCERTAIN", "R9"),
    ("REVIEWED good description",    "Contract_Start__c", "Date", GOOD, [], "REVIEWED", None),
    # Known fixes — do not revert
    ("fix 1: no bare 'na' (inactive)", "Status_Note__c", "Text", "Explains why an inactive international account was closed by finance.", [], "REVIEWED", None),
    ("fix 2: date range is R8, not R3", "Season__c", "Date",     "Date range of the season in which the account places its bulk orders.", [], "UNCERTAIN", "R8"),
    ("fix 3: short 'TBD' reaches R5", "Region__c",   "Text",     "TBD", [], "FLAGGED", "R5"),
    ("fix 4: YYYY-MM-DD not jargon",  "Ship_Date__c", "Date",    "Planned ship date in YYYY-MM-DD format, set by the warehouse system.", [], "REVIEWED", None),
    ("fix 6: ID format code is not jargon", "RA_Number__c", "Text", "Return authorisation code issued by the returns team. Format: RA-XXXXXXXX.", [], "REVIEWED", None),
    ("fix 6: currency code is not jargon", "Big_Deal__c", "Checkbox", "Checked for deals above CHF 100,000, which need an executive sponsor.", [], "REVIEWED", None),
    ("R7 six-letter acronym",        "Score__c",     "Number",   "MEDDIC qualification score assigned by the account executive during discovery.", [], "UNCERTAIN", "R7"),
    ("fix 7: 'task' is not the placeholder 'ask'", "End_Date__c", "Date", "Expiry date of the supply agreement. Triggers a renewal task 90 days before this date.", [], "REVIEWED", None),
    ("fix 7: picklist value 'A' needs a whole word", "Grade__c", "Picklist", "Grade assigned to the customer based on their value and engagement.", ["A", "B", "C"], "FLAGGED", "R4"),
    ("R3 text field described as dropdown", "Contact_Time__c", "Text", "Select the time window when this contact prefers to be called: Morning or Evening.", [], "FLAGGED", "R3"),
    ("R8 date field holds a list",   "Deadline__c",  "Date",     "Stores the list of deadlines applicable to this case for response and resolution.", [], "UNCERTAIN", "R8"),
    ("R8 currency field holds a count", "Units__c",  "Currency", "Number of product units expected in this order, as estimated by the sales rep.", [], "UNCERTAIN", "R8"),
    ("fix 5: picklist placeholder reaches R5", "Data_Residency__c", "Picklist", "TODO - confirm with legal before enabling.", ["EU", "US", "APAC"], "FLAGGED", "R5"),
]


def main() -> int:
    failures = 0
    for name, api_name, ftype, desc, picklist, exp_status, exp_rule in CASES:
        field  = {"field_api_name": api_name, "field_type": ftype,
                  "description": desc, "picklist_values": picklist}
        result = script1._classify_one(field, include_standard=False)
        got    = (result["status"], result["rule"])
        if got == (exp_status, exp_rule):
            print(f"PASS  {name}")
        else:
            failures += 1
            print(f"FAIL  {name}: expected {exp_status}/{exp_rule}, got {got[0]}/{got[1]}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
