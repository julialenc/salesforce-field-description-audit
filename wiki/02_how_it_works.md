# How the Tool Works

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
                              data/`sf_classified.json`
                          (all fields, one status each)
                                             ↓

                        Shared prompt context
                (assembled once per session for all LLM calls)
                         ┌───────────────────────────────┐
                         │ `system_prompt.md`            │
                         │ universal rules for           │
                         │ good field descriptions       │
                         ├───────────────────────────────┤
                         │ `golden_examples.json`        │
                         │ curated high-quality examples │
                         │ for few-shot grounding        │
                         └───────────────────────────────┘
                                             ↓

                 ┌───────────────────────────┼────────────────────────┐
                 ↓                           ↓                        ↓
             FLAGGED                     UNCERTAIN               PASSED + SKIPPED
                 ↓                           ↓                        ↓
           Prompt A                      Prompt B                  No LLM
    "If the description          "Is this description         PASSED fields used
    is missing, write a           good enough?                 as few-shot examples
    new one from metadata.        If not, suggest              in Prompt A and B.
    If it exists, replace         an improvement."             SKIPPED logged only.
    it with a better one."
                 ↓                           ↓                        ↓
      Shared prompt context        Shared prompt context
       + Prompt A + fields          + Prompt B + fields
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
[4] `review_queue_{timestamp}.xlsx` — three tabs, one row per field
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
                    `write_log_{timestamp}.xlsx`
                    (record of every change made)

</pre>


### Step 1 — Ingestion
`01_ingest_classify_send.py`

Script 1 begins by reading `config.yml` to determine the runtime setup for the current run, including which Salesforce objects should be processed.

The repository provides `config.example.yml` as a safe, shareable template. It shows the full configuration structure, including the values each user needs to supply and the object list to scan.

Once the object list is confirmed, the script connects to Salesforce using the **Tooling API** and pulls field metadata for every field on those objects. For each field, it retrieves:

- **Field label**
- **Field API name**
- **Field type**
- **Picklist values** *(if applicable)*
- **Existing description**

By default, the tool processes **custom fields only** — those ending in `__c`. **Standard fields can be included per object** by enabling an option in `config.yml`. A small subset of standard fields is read-only in Salesforce and cannot be updated regardless of this setting — these are logged as **SKIPPED** and never touched.

The raw metadata is saved locally as `sf_metadata_raw.json` before any processing begins. This file is kept for traceability — it represents exactly what Salesforce returned at the time of the scan.

> **This step is entirely read-only. Nothing is written to Salesforce.**

---

### Step 2 — Classification
`01_ingest_classify_send.py`

Every field collected in Step 1 is evaluated by a Python classifier against **10 rule-based checks**, which are described at the end of this chapter.

Based on the results, every field is assigned one of four statuses:

| Status | What it means |
|---|---|
| **FLAGGED** | The description has a clear, detectable problem. The classifier is certain. The LLM will be asked to propose a replacement description. |
| **UNCERTAIN** | The description may have a problem, but context or judgment is needed to confirm. The LLM will be asked to evaluate the description and propose a replacement only if the problem is confirmed. |
| **PASSED** | The description looks acceptable. No LLM involvement. No changes proposed. |
| **SKIPPED** | The field is a Salesforce system field that cannot be updated via API. Logged for visibility only. Never sent to LLM. Never written to. |

A field receives exactly one status. If multiple checks trigger on the same field, the most severe status wins — **FLAGGED takes priority over UNCERTAIN**.

### Rule Evaluation Order and Status Priority

The classifier does **not** treat all 10 rules as equal, and it does **not** always evaluate every field against all 10 rules.

Instead, the rules are checked in a deliberate order from the **strongest and most certain failures** to the **softest and most context-dependent failures**.

This serves two purposes:

- it makes classification more **efficient**
- it makes the final status more **predictable and reproducible**

#### Status priority

A field can receive only one final status:

- `SKIPPED`
- `FLAGGED`
- `UNCERTAIN`
- `PASSED`

If multiple rules could apply to the same field, the most severe status wins.

The priority is:

`SKIPPED` → `FLAGGED` → `UNCERTAIN` → `PASSED`

That means:
- a field that cannot be written to is marked `SKIPPED` immediately
- a field with any clear failure is marked `FLAGGED`
- a field with no clear failure but with weaker signals is marked `UNCERTAIN`
- only a field that triggers none of the checks is marked `PASSED`

#### Evaluation hierarchy

The rules are evaluated in this order:

##### First: immediate stop conditions

These checks are either high-confidence failures or hard exclusions. As soon as one of them applies, the classifier stops and assigns the result immediately.

1. **SKIPPED** — the field is not writable or intentionally excluded from write-back
2. **NULL**
3. **Echo / Too Short**
4. **Stale or Placeholder**
5. **Audience Mismatch**
6. **Wrong Type Hint**
7. **Undefined Picklist**

All of these produce `FLAGGED` except `SKIPPED`, which remains its own status.

##### Second: softer checks

If none of the stronger checks apply, the classifier evaluates the softer, more context-dependent rules:

8. **Too Long**
9. **Contradictory**
10. **Jargon Without Context**
11. **Ambiguous**

These produce `UNCERTAIN`.

If one or more of these checks apply, the field is marked `UNCERTAIN`.

If none apply, the field is marked `PASSED`.

#### Why the classifier stops early

The classifier is intentionally designed to stop as soon as a strong `FLAGGED` condition is found.

For example:

- if a description is completely empty, there is no value in also checking whether it is too long or ambiguous
- if a Picklist description clearly fails to explain the values, that strong failure takes priority over weaker signals such as excessive length
- if a field is not writable, the classifier marks it `SKIPPED` immediately and does not continue evaluation

This makes the runtime more efficient, especially when processing large numbers of fields, and avoids generating multiple competing statuses for the same row.

> The LLM does not rewrite anything at this stage. Classification is fully rule-based and deterministic. The LLM is only involved in the next step.

### Classifier Output

The result of classification is saved locally as `data/sf_classified.json`.
This file contains every field processed in Step 1, each annotated with its assigned status:
`FLAGGED`, `UNCERTAIN`, `PASSED`, or `SKIPPED`.

All statuses are stored in a single file. The split into Prompt A (FLAGGED) and Prompt B (UNCERTAIN) happens at runtime in the next step — not at storage. PASSED fields are also read from this file when building few-shot examples for the LLM.

This file is the single source of truth between the classification step and the LLM step.

---

### Step 3 — LLM Routing and Processing
`01_ingest_classify_send.py`

The input for this step is `data/sf_classified.json` — the file produced by the Classifier in Step 2. Every field in that file carries a status: `FLAGGED`, `UNCERTAIN`, `PASSED`, or `SKIPPED`.

Before any fields are sent to the LLM, Script 1 assembles a reusable instruction layer for the session:

- `system_prompt.md` — the universal definition of a good field description, including the expected tone, length, format, and quality criteria
- `golden_examples.json` — a curated set of high-quality field descriptions used for few-shot grounding

This shared context is injected once per session. For each batch, the script then adds the relevant task instruction — `prompt_a_flagged_fields.md` or `prompt_b_uncertain_fields.md` — together with the field data for that batch.

Routing logic:

| Status | What happens |
|---|---|
| **FLAGGED** | Sent to the LLM with `prompt_a_flagged_fields.md` — if the description is missing, the LLM writes a new one from metadata; if the description exists but is unusable, the LLM replaces it |
| **UNCERTAIN** | Sent to the LLM with `prompt_b_uncertain_fields.md` — the LLM evaluates the existing description and suggests an improvement only if one is needed |
| **PASSED** | Not sent to the LLM — carried forward without change |
| **SKIPPED** | Not sent to the LLM — logged for visibility only and carried forward without change |

Fields are sent in batches of 50 per API call. Raw responses are written to `data/llm_response.json` before any further processing. This ensures that if anything fails downstream, the LLM output is not lost.

---

### Step 4 — Merge and Output
`01_ingest_classify_send.py`

Once all LLM responses are received and stored in `data/llm_response.json`, the script merges them with the original classified data from `data/sf_classified.json` and assembles a single Excel file for human review:

`review_queue_{timestamp}.xlsx`

The file contains three tabs:

| Tab | Contents | Reviewer action required |
|---|---|---|
| **Tab A — FLAGGED** | Original description + AI-written replacement | Approve, edit, or reject each row |
| **Tab B — UNCERTAIN** | Original description + AI-suggested revision | Approve, edit, or reject each row |
| **Tab C — PASSED / SKIPPED** | Original description only, no AI suggestion | No action required — included for full visibility |

The timestamp in the filename ensures that multiple runs do not overwrite each other, and every review file can be traced back to the exact run that produced it.

This file is a proposal, not an action.

---

### Step 5 — Human Review *(manual step)*
`data/review_queue_{timestamp}.xlsx`

The Admin opens `data/review_queue_{timestamp}.xlsx` and works through **Tab A** and **Tab B** — one row per field. For every row, the Admin enters one of three decisions in the **Approve / Edit / Reject** column:

| Decision | What it means | What happens next |
|---|---|---|
| **Approve** | The AI suggestion is accepted as written | Script 2 will write it to Salesforce exactly as shown |
| **Edit** | The AI suggestion needs adjustment | Admin writes the preferred description in the **Admin Version** column. Script 2 will use that text instead. |
| **Reject** | The AI suggestion is discarded | Script 2 skips this field. Nothing is written to Salesforce. |

> Every row in Tab A and Tab B must have a decision before Script 2 can run.
> Script 2 will not proceed if any decision is missing.

Once all rows have a decision, the Admin saves the file. The filename must not be changed — Script 2 identifies the correct file by its name and timestamp.

> **Nothing in this step touches Salesforce. The review file is a proposal, not an action.**

---

### Step 6 — Write-Back
`02_deploy_approved.py`

Script 2 begins with a validation pass before writing anything. It checks that:

- Every row in Tab A and Tab B has a value in the **Approve / Edit / Reject** column
- Every row marked **Edit** has a non-empty value in the **Admin Version** column
- No approved or edited description exceeds 255 characters — the Salesforce field limit

If any of these checks fail, the script stops and reports the problem. Nothing is written to Salesforce until the file passes validation in full.

Once validation passes, the script processes each row according to the Admin's decision:

| Decision | What Script 2 does |
|---|---|
| **Approve** | Writes the value from the **LLM Suggestion** column to Salesforce |
| **Edit** | Writes the value from the **Admin Version** column to Salesforce |
| **Reject** | Skips the field — no change is made |

Write-back is performed using the **Metadata API** via `02_deploy_approved.py`. Each field is updated individually. If a single field update fails — for example due to a permissions issue or a locked field — the script logs the failure and continues processing the remaining fields. A partial failure does not stop the run.

Every field processed in this step is recorded in:

`data/write_log_{timestamp}.xlsx`

This file is the audit trail for attempted writes and their outcomes.

> This log is the audit trail for every change made to Salesforce. Keep it.

---

## The 10 Rule-based Checks

### Rule 1 — NULL
**The description is completely empty.**

The field has never been given a description. There is nothing to evaluate.

---

### Rule 2 — Echo / Too Short
**The description just repeats the field name, or is too short to be meaningful.**

Examples: a field labelled `Customer Tier` with a description of `Customer Tier` or `Tier`.
A description under a minimum character threshold with no real content.

---

### Rule 3 — Stale or Placeholder
**The description contains placeholder language or is clearly outdated.**

Examples: *"TBD"*, *"to be confirmed"*, *"ask John"*, *"deprecated"*, *"no longer used"*.
These were acceptable temporarily. In a live org read by AI, they are liabilities.

---

### Rule 4 — Audience Mismatch
**The description is written for end users, not for systems.**

Example: *"Click here to select the account type. Choose the option that best describes
your customer."* Field descriptions in Salesforce are not help text or tooltips.
They are read by integrations, AI agents, and developers — not by the people filling in forms.

---

### Rule 5 — Wrong Type Hint
**The description contradicts the field type.**

Example: a Checkbox field described as *"Enter the customer's preferred contact method"*.
Checkboxes store true/false values, not contact preferences.
The description suggests the wrong data type, which misleads any system reading the metadata.

---

### Rule 6 — Undefined Picklist
**The field is a Picklist, but the description does not reference the values or their meaning.**

Example: a Picklist field with values `Tier 1`, `Tier 2`, `Tier 3` and a description of
*"Indicates the customer tier"*. Without knowing what Tier 1 or Tier 3 means, the description
is incomplete. An AI reading this cannot interpret the values correctly.

---

### Rule 7 — Too Long
**The description exceeds a reasonable length and likely contains noise.**

Salesforce allows up to 255 characters. Descriptions that approach or exceed this limit
often contain instructions, historical notes, or multiple meanings merged into one field.
This may indicate the field is doing too much, or the description was never maintained.

---

### Rule 8 — Contradictory
**The description conflicts with something else observable in the metadata.**

Example: a field described as *"Always required at case creation"* that is not marked
as required in Salesforce. Or a field described as *"Populated automatically by the system"*
that has no automation attached.

---

### Rule 9 — Jargon Without Context
**The description uses internal acronyms or terms that are not explained.**

Example: *"Used by the SFMC sync for BU segmentation"*.
An AI — or a new team member — cannot interpret `SFMC` or `BU` without context.
Internal shorthand that has never been documented creates silent knowledge gaps.

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

---
