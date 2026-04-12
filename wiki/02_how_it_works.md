
## How the Tool Works

### High-Level Process Overview

<pre>
Salesforce Org
      ↓
[1] Extract field metadata — Tooling API
      ↓
[2] Classify the description of every field — 10 rule-based checks (described at the end of the file)
      ↓                          ↓                        ↓                        ↓
  FLAGGED                   UNCERTAIN                  PASSED                  SKIPPED
(clear failure)         (possible failure)           (no issues)          (system fields —
                                                                          read-only, cannot
                                                                          be overwritten)
      ↓                          ↓                        ↓                        ↓
      └──────────────────────────┴────────────────────────┴────────────────────────┘
                                             ↓
                              data/sf_classified.json
                          (all fields, one status each)
                                             ↓
                 ┌───────────────────────────┼────────────────────────┐
                 ↓                           ↓                        ↓
             FLAGGED                     UNCERTAIN               PASSED + SKIPPED
                 ↓                           ↓                        ↓
           Prompt A                      Prompt B                  No LLM
    "This description             "Is this description         PASSED fields used
    is bad. Write                 good enough?                 as few-shot examples
    a better one."                If not, suggest              in Prompt A and B.
                                  an improvement."             SKIPPED logged only.
                 ↓                           ↓
          Sent to AI                  Sent to AI
                 ↓                           ↓
          AI writes a              AI evaluates and
          new description          suggests a revision
                 ↓                           ↓
                 └──────────┬───────────────┘
                            ↓
[3] Merge all results — FLAGGED + UNCERTAIN + PASSED + SKIPPED
                            ↓
[4] review_queue_{timestamp}.xlsx — three tabs, one row per field
         Tab A — Fields that were FLAGGED (AI wrote a new description)
         Tab B — Fields that were UNCERTAIN (AI suggested a revision)
         Tab C — Fields that PASSED or were SKIPPED (no action needed, for reference only)
                            ↓
                    ── HUMAN STEP ──
[5] Admin opens the spreadsheet and reviews Tab A and Tab B
    For every row: Approve / Edit / Reject the AI suggestion
                            ↓
[6] Admin saves the completed file and triggers Script 2
                            ↓
[7] Script 2 reads decisions and writes approved descriptions
    back to Salesforce — Metadata API
                            ↓
                    write_log_{timestamp}.xlsx
                    (record of every change made)
</pre>


### Step 1 — Ingestion
`01_ingest_classify_send.py`

Script 1 begins by reading `config.yml` to determine which Salesforce objects to process.
This is the only file an Admin needs to edit before running the tool. It contains the list
of object names — for example Account, Contact, Case — and nothing else.

Once the object list is confirmed, the script connects to Salesforce using the **Tooling API**
and pulls the field metadata for every field on those objects. For each field, it retrieves:

- **Field label** *(the name users see in Salesforce)*
- **Field API name** *(the technical identifier used in code and integrations)*
- **Field type** *(Text, Number, Picklist, Checkbox, etc.)*
- **Picklist values** *(if applicable — used later to write more accurate descriptions)*
- **Existing description** *(blank if none has ever been written)*

By default, the tool processes **custom fields only** — those ending in `__c`. **Standard fields
can be included per object** by enabling an option in `config.yml`. Note that a small subset of
standard fields is read-only in Salesforce and cannot be updated regardless of this setting —
these are logged as **SKIPPED** and never touched.

The raw metadata is saved locally as `sf_metadata_raw.json` before any processing begins.
This file is kept for traceability — it represents exactly what Salesforce returned at the
time of the scan.

> **This step is entirely read-only. Nothing is written to Salesforce.**

### Step 2 — Classification
`01_ingest_classify_send.py`

Every field collected in Step 1 is evaluated by a Python classifier against **10 rule-based
checks**, which are described at the end of this chapter. Each check looks at the **field description only** — not the field name, label, or type.
Based on the results, every field is assigned one of four statuses:

| Status | What it means |
|---|---|
| **FLAGGED** | The description has a clear, detectable problem. The classifier is certain. The LLM will be asked to propose a replacement description. |
| **UNCERTAIN** | The description may have a problem, but context or judgment is needed to confirm. The LLM will be asked to evaluate the description and propose a replacement only if the problem is confirmed. |
| **PASSED** | The description looks acceptable. No LLM involvement. No changes proposed. |
| **SKIPPED** | The field is a Salesforce system field that cannot be updated via API. Logged for visibility only. Never sent to LLM. Never written to. |

A field receives exactly one status. If multiple checks trigger on the same field, the most
severe status wins — **FLAGGED takes priority over UNCERTAIN**.

> The LLM does not rewrite anything at this stage. Classification is fully rule-based and
> deterministic. The LLM is only involved in the next step.

### Classifier Output

The result of classification is saved locally as `data/sf_classified.json`.
This file contains every field processed in Step 1, each annotated with its assigned status:
`FLAGGED`, `UNCERTAIN`, `PASSED`, or `SKIPPED`.

All statuses are stored in a single file. The split into Prompt A (FLAGGED) and Prompt B
(UNCERTAIN) happens at runtime in the next step — not at storage. PASSED fields are also
read from this file when building few-shot examples for the LLM.

This file is the single source of truth between the classification step and the LLM step.

---







## The 10 Rule-based Checks

---

### Rule 1 — NULL
**The description is completely empty.**

The field has never been given a description. There is nothing to evaluate.

| Classifier verdict | FLAGGED |
|---|---|

---

### Rule 2 — Echo / Too Short
**The description just repeats the field name, or is too short to be meaningful.**

Examples: a field labelled `Customer Tier` with a description of `Customer Tier` or `Tier`.
A description under a minimum character threshold with no real content.

| Classifier verdict | FLAGGED |
|---|---|

---

### Rule 3 — Wrong Type Hint
**The description contradicts the field type.**

Example: a Checkbox field described as *"Enter the customer's preferred contact method"*.
Checkboxes store true/false values, not contact preferences.
The description suggests the wrong data type, which misleads any system reading the metadata.

| Classifier verdict | FLAGGED |
|---|---|

---

### Rule 4 — Undefined Picklist
**The field is a Picklist, but the description does not reference the values or their meaning.**

Example: a Picklist field with values `Tier 1`, `Tier 2`, `Tier 3` and a description of
*"Indicates the customer tier"*. Without knowing what Tier 1 or Tier 3 means, the description
is incomplete. An AI reading this cannot interpret the values correctly.

| Classifier verdict | FLAGGED |
|---|---|

---

### Rule 5 — Too Long
**The description exceeds a reasonable length and likely contains noise.**

Salesforce allows up to 255 characters. Descriptions that approach or exceed this limit
often contain instructions, historical notes, or multiple meanings merged into one field.
This may indicate the field is doing too much, or the description was never maintained.

| Classifier verdict | UNCERTAIN |
|---|---|

---

### Rule 6 — Stale or Placeholder
**The description contains placeholder language or is clearly outdated.**

Examples: *"TBD"*, *"to be confirmed"*, *"ask John"*, *"deprecated"*, *"no longer used"*.
These were acceptable temporarily. In a live org read by AI, they are liabilities.

| Classifier verdict | FLAGGED |
|---|---|

---

### Rule 7 — Jargon Without Context
**The description uses internal acronyms or terms that are not explained.**

Example: *"Used by the SFMC sync for BU segmentation"*.
An AI — or a new team member — cannot interpret `SFMC` or `BU` without context.
Internal shorthand that has never been documented creates silent knowledge gaps.

| Classifier verdict | UNCERTAIN |
|---|---|

---

### Rule 8 — Contradictory
**The description conflicts with something else observable in the metadata.**

Example: a field described as *"Always required at case creation"* that is not marked
as required in Salesforce. Or a field described as *"Populated automatically by the system"*
that has no automation attached.
These contradictions cannot be resolved by the tool — they require a human decision.

| Classifier verdict | UNCERTAIN |
|---|---|

---

### Rule 9 — Audience Mismatch
**The description is written for end users, not for systems.**

Example: *"Click here to select the account type. Choose the option that best describes
your customer."* Field descriptions in Salesforce are not help text or tooltips.
They are read by integrations, AI agents, and developers — not by the people filling in forms.
UI instructions in a field description add noise and no signal.

| Classifier verdict | FLAGGED |
|---|---|

---

### Rule 10 — Ambiguous
**The description exists, is the right length, and sounds reasonable — but means nothing specific.**

Examples:
- *"Contains additional information about the source"*
- *"Used to categorize the record"*

The ambiguity test: remove the field name and object name from the description.
What remains should still tell you something specific about the data.
If it could describe any field in any system, it fails.

This is the hardest problem to catch with rules alone. It requires understanding meaning,
not just checking for missing values. That is why it is routed to the LLM for evaluation
rather than flagged with certainty.

| Classifier verdict | UNCERTAIN |
|---|---|

---

## Classification Summary

| # | Problem Type | Classifier Verdict |
|---|---|---|
| 1 | NULL | FLAGGED |
| 2 | Echo / Too Short | FLAGGED |
| 3 | Wrong Type Hint | FLAGGED |
| 4 | Undefined Picklist | FLAGGED |
| 5 | Too Long | UNCERTAIN |
| 6 | Stale or Placeholder | FLAGGED |
| 7 | Jargon Without Context | UNCERTAIN |
| 8 | Contradictory | UNCERTAIN |
| 9 | Audience Mismatch | FLAGGED |
| 10 | Ambiguous | UNCERTAIN |

