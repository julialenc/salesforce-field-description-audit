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
- Preserve all other content in the description.

**R8 — Contradictory configuration**
The description conflicts with what the field type can store. For example: a Date field described as storing a range, an Email field described as storing multiple addresses, a Checkbox described as storing written text. Rewrite the description to match what the field type actually stores.

- `action`: `"rewrite"`
- Preserve the business intent of the original description. Only fix the structural contradiction.

**R9 — Audience mismatch**
The description is written as a UI instruction for the person filling in the form, not as a metadata description for systems and developers. Rewrite in third person, passive voice where appropriate, describing what the field stores and what it drives — not what a user should do.

Bad: `"Use the dropdown to select how the customer prefers to be contacted. Make sure to update this field after every customer call."`
Good: `"Preferred communication channel for this contact. Values: Email, Phone, SMS, Post. Used by the marketing automation platform to route outbound messages to the correct delivery channel."`

- `action`: `"rewrite"`
- Preserve the factual content. Only fix the audience and voice.

---

## What to Preserve

In all cases, preserve:
- Specific system names, workflow names, or integration names
- Exact field names referenced (e.g. `Last_Order_Date__c`)
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
    "field_api_name": "Stakeholder_Map_Notes__c",
    "action": "shorten",
    "suggested_description": "Free-text field storing the stakeholder map for this opportunity, including buyer roles, support level, internal dynamics, and the engagement strategy agreed between the AE and manager.",
    "reasoning": "R6: original was 214 chars; shortened to 178 chars without removing any key content."
  },
  {
    "field_api_name": "NPS_Segment__c",
    "action": "rewrite",
    "suggested_description": "NPS (Net Promoter Score) segment assigned to this contact after the quarterly survey cycle. Values: Detractor, Passive, Promoter. Used to prioritise re-engagement and customer success outreach.",
    "reasoning": "R7: NPS was unexplained; expanded inline and added values and usage context."
  },
  {
    "field_api_name": "Primary_Contact_Email__c",
    "action": "rewrite",
    "suggested_description": "Primary email address for the main contact at this account. Used for transactional notifications and account-level correspondence. For multiple contacts, use the related Contact records.",
    "reasoning": "R8: Email field cannot store a list; rewrote to reflect single-value storage and redirected multi-contact use case."
  },
  {
    "field_api_name": "Newsletter_Opt_In__c",
    "action": "rewrite",
    "suggested_description": "Checked when this contact has opted in to receive the monthly newsletter and promotional emails. Requires explicit written consent. Drives inclusion in newsletter distribution lists in the marketing automation platform.",
    "reasoning": "R9: original was a UI instruction; rewritten as a system-oriented description in third person."
  }
]
```

**Length:**
- For R6 (shorten): target 60–200 characters. Must be shorter than the original.
- For R7, R8, R9 (rewrite): aim for 60–180 characters. Do not exceed 255 characters.
