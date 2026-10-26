# Prompt B — UNCERTAIN Fields

## Your Task

You are receiving a batch of Salesforce fields whose descriptions have been automatically classified as **UNCERTAIN**. Each field has a description that exists and passed basic quality checks, but has a specific detected issue that may reduce its usefulness for AI agents, integrations, or developers.

**For every field in the batch: evaluate the description and suggest an improvement.**

Unlike FLAGGED fields, UNCERTAIN fields have descriptions that contain some useful content. Your job is to fix the specific detected issue while preserving what is already correct.

---

## What Each Rule Means

The classifier assigned one of four rules. The rule tells you exactly what to fix:

**R6 — Too long (>200 characters)**
The description exceeds 200 characters. It is not wrong — it is too verbose. Shorten it without losing meaning, specificity, or any critical detail. The shortened version must remain within 30–200 characters. Do not remove picklist values, field name references, thresholds, or system names. Remove redundant phrasing, filler clauses, and process detail that does not help a developer understand what the field stores.

- `action`: `"shorten"`
- Do not change the meaning. Do not introduce new content.

**R7 — Jargon without context**
The description contains an unexplained acronym or internal term. Expand the acronym inline on first use using the format: `ACRONYM (Full Name)`. If you do not know what the acronym stands for, do not guess — note in your reasoning that the expansion is unknown and rewrite the description to remove or replace the term with plain language.

- `action`: `"rewrite"`
- Preserve all other content in the description, unless the expansion pushes the result over 255 characters. The 255-character limit wins: then shorten process detail (who populates it, how it is checked) and keep what the field stores, formats, thresholds and values.

**R8 — Contradictory configuration**
The description conflicts with what the field type can store. For example: a Date field described as storing a range, an Email field described as storing multiple addresses, a Checkbox described as storing written text. Rewrite the description to match what the field type actually stores.

- `action`: `"rewrite"`
- Preserve the business intent of the original description. Only fix the structural contradiction, and remove the words that describe the impossible structure rather than qualifying them.

**R9 — Audience mismatch**
The description is written as a UI instruction for the person filling in the form, not as a metadata description for systems and developers. Rewrite in third person, passive voice where appropriate, describing what the field stores and what it drives — not what a user should do.

Bad: `"Choose the customer's time zone from the list so you know when to call them. Remember to update it if they move."`
Good: `"Time zone of this contact's main office as a region/city name (e.g. Europe/Zurich). Read by the meeting scheduler to propose call slots inside local business hours."`

- `action`: `"rewrite"`
- Preserve the factual content. Only fix the audience and voice.

---

## What to Preserve

In all cases, preserve:
- Specific system names, workflow names, or integration names
- Exact field names referenced (e.g. `Last_Invoice_Date__c`)
- Specific thresholds, formats, or values already stated
- Picklist values — if already listed in the description, keep them; if the field is a Picklist and values are in `picklist_values`, add them if missing

Do not introduce generic language to replace specific content that was already present.

---

## Input Format

You will receive a JSON array. Each element contains:
- `field_api_name` — the Salesforce API name of the field
- `field_type` — the Salesforce field type
- `description` — the current description (exists, has some useful content)
- `picklist_values` — list of values if the field is a Picklist or MultiselectPicklist (may be empty)
- `formula` — the formula expression if Formula type (otherwise null)
- `related_object` — the target object if Lookup or MasterDetail (otherwise null)
- `rule_triggered` — the classifier rule: R6, R7, R8, or R9

## Output Format

Return a JSON array in the same order as the input.

```json
[
  {
    "field_api_name": "Site_Visit_Notes__c",
    "action": "shorten",
    "suggested_description": "Free-text notes from on-site visits to this account: attendees, equipment inspected, issues found and agreed follow-up actions.",
    "reasoning": "R6: original was 236 chars; shortened to 127 chars without removing any key content.",
    "assumptions": [],
    "missing": []
  },
  {
    "field_api_name": "MTBF_Hours__c",
    "action": "rewrite",
    "suggested_description": "MTBF (Mean Time Between Failures) of this installed machine in operating hours, calculated from its service history. A value below 500 hours triggers a preventive maintenance proposal.",
    "reasoning": "R7: MTBF was unexplained; expanded inline and kept the 500-hour threshold.",
    "assumptions": [],
    "missing": []
  },
  {
    "field_api_name": "Invoice_Email__c",
    "action": "rewrite",
    "suggested_description": "Single email address that receives invoices for this account. Further invoice recipients are stored as Contact records with the Billing role.",
    "reasoning": "R8: an Email field cannot store a list; rewrote it as a single address and pointed further recipients to Contact records.",
    "assumptions": [],
    "missing": []
  },
  {
    "field_api_name": "Paperless_Billing__c",
    "action": "rewrite",
    "suggested_description": "Checked when this account has agreed in writing to receive invoices by email only. Stops the billing system from printing and posting paper invoices.",
    "reasoning": "R9: original was a UI instruction; rewritten as a system-oriented description in third person.",
    "assumptions": [],
    "missing": []
  }
]
```

**Length:**
- For R6 (shorten): target 60–200 characters. Must be shorter than the original.
- For R7, R8, R9 (rewrite): aim for 60–180 characters. Do not exceed 255 characters.

---

## Check Before You Answer

Read each `suggested_description` once more and fix it if any of these fail:
1. **Length:** at most 255 characters, counted including spaces. If it is longer, cut process detail, not facts.
2. **Acronyms:** every acronym is expanded in brackets on first use, e.g. "NPS (Net Promoter Score)". This includes acronyms taken from the field name (NPS, RFM, EBR). Picklist values are written exactly as given and need no expansion. If you do not know what an acronym stands for, write the idea in plain words instead. Do not add acronyms that are not in the input.
3. **Forbidden terms:** none of "relevant", "applicable", "various", "related to", "for tracking", "for reporting", "for reference", "internal use". Name the specific report, team, rule or system instead, or leave the clause out.
4. **Picklist values:** every value from `picklist_values` appears, spelled exactly as given.
5. **R6 only:** at most 200 characters and shorter than the original. Do not keep the "including a, b, c, d" list form: summarise the list in a few words or keep only the items a developer needs.
6. **R8 only:** the words that describe the impossible structure ("list of", "range", "written feedback", "multiple addresses") are gone, not just qualified.
7. **Assumptions:** every person, team, process, system or consequence you added is either in the input or listed in `assumptions`. A shorten never adds anything, so its list is `[]`.
