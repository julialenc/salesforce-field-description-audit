# How the Tool Works



### High-Level Process Overview

<pre>
Salesforce Org
      ↓
[1] Extract field metadata — Tooling API
      ↓
[2] Classify the description of every field — 10 rule-based checks (described at the end of this file)
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
---
      
### Step 1 — Ingestion

`01_ingest_classify_send.py`

Script 1 begins by reading `config.yml` to determine the runtime setup for the current run, including which Salesforce objects should be processed.

The repository provides `config.example.yml` as a safe, shareable template. It shows the full configuration structure, including the values each user needs to supply and the object list to scan.

Once the object list is confirmed, the script connects to Salesforce using the **Tooling API** and pulls field metadata for every field on those objects. For each field, it retrieves:

* **Field label**
* **Field API name**
* **Field type**
* **Picklist values** *(if applicable)*
* **Existing description**

By default, the tool processes **custom fields only** — those ending in `__c`. **Standard fields can be included per object** by enabling an option in `config.yml`. A small subset of standard fields is read-only in Salesforce and cannot be updated regardless of this setting — these are logged as **SKIPPED** and never touched.

The raw metadata is saved locally as `sf_metadata_raw.json` before any processing begins. This file is kept for traceability — it represents exactly what Salesforce returned at the time of the scan.

In **experiment mode**, the Tooling API call is replaced by reading from a local JSON file. Two versions of this file exist for experiment purposes:

* `data/sf_metadata_raw_training.json` — the **training set**, used during classifier development and prompt iteration
* `data/sf_metadata_raw_test.json` — the **test set**, used only for final validation once classifier and prompts are considered stable

Which file is active is controlled by `data_source.experiment_file` in `config.yml`. See wiki `03_experiment_and_validation.md` for the full experiment methodology.

> \*\*This step is entirely read-only. Nothing is written to Salesforce.\*\*

---

### Step 2 — Classification

`01_ingest_classify_send.py`

Every field collected in Step 1 is evaluated by a Python classifier against **10 rule-based checks**, which are described in full at the end of this chapter.

Based on the results, every field is assigned one of four statuses:

|Status|What it means|
|-|-|
|**FLAGGED**|The description has a clear, detectable problem. The classifier is certain. The LLM will be asked to propose a replacement description.|
|**UNCERTAIN**|The description may have a problem, but context or judgment is needed to confirm. The LLM will be asked to evaluate the description and propose a replacement only if the problem is confirmed.|
|**PASSED**|The description looks acceptable. No LLM involvement. No changes proposed.|
|**SKIPPED**|The field is a Salesforce system field that cannot be updated via API. Logged for visibility only. Never sent to LLM. Never written to.|

A field receives exactly one status. If multiple checks could apply to the same field, the earliest check to fire wins — the classifier stops immediately and does not continue evaluating that field.

### Rule Evaluation Order and Status Assignment

The classifier evaluates rules in a fixed two-step sequence. The structure of the sequence determines whether a field is FLAGGED or UNCERTAIN — it is not possible for a Step 1 rule to produce UNCERTAIN, or for a Step 2 rule to produce FLAGGED.

#### Rules 1 through 5 (FLAGGED)

These rules represent clear, high-confidence failures. They are checked first, in order. The first rule that fires assigns the field a status of **FLAGGED** and stops all further evaluation for that field.

|Rule|Name|What it detects|
|-|-|-|
|R1|NULL / Blank|Description is missing or whitespace-only|
|R2|Echo / Too Short|Description restates the field name or contains too little content|
|R3|Wrong Type Hint|Description contradicts the field type|
|R4|Undefined Picklist|Picklist field whose description ignores the values entirely|
|R5|Stale or Placeholder|Description contains placeholder language (TBD, TODO, deprecated, N/A)|

If a field triggers any of Rules 1–5, it is marked **FLAGGED**. The Rule Column records the first rule that fired. Step 2 is not evaluated.

#### Rules 6 through 10 (UNCERTAIN)

These rules are only evaluated if the field has passed all of Step 1. They represent softer, more context-dependent signals. The first rule that fires assigns the field a status of **UNCERTAIN** and stops all further evaluation for that field.

|Rule|Name|What it detects|
|-|-|-|
|R6|Too Long|Description exceeds 200 characters — not necessarily wrong, but a candidate for shortening to improve token efficiency for Agentforce|
|R7|Jargon Without Context|Description uses unexplained internal acronyms or terms|
|R8|Contradictory|Description conflicts with something else observable in the field configuration|
|R9|Audience Mismatch|Description is written for end users rather than systems or developers|
|R10|Ambiguous|Description exists and passes all prior checks but is too vague to be actionable|

If a field triggers any of Rules 6–10, it is marked **UNCERTAIN**. If none trigger, the field is marked **PASSED**.

#### Why the classifier stops at the first match

The classifier is designed to stop as soon as a rule fires, rather than continuing to accumulate all matching rules for a given field.

This has two benefits:

* **Efficiency** — there is no value in checking whether a blank description is also too long
* **Predictability** — each field has exactly one assigned rule, making classifier output easier to audit and the LLM prompt easier to construct

When a field could plausibly trigger multiple rules, the rule that fires first in the sequence is the one recorded. The assigned status follows that rule's step.

#### Evaluation summary

```
For each field:
  Is it a system field (non-writable)?  → SKIPPED. Stop.
  Does R1 fire?  → FLAGGED / R1. Stop.
  Does R2 fire?  → FLAGGED / R2. Stop.
  Does R3 fire?  → FLAGGED / R3. Stop.
  Does R4 fire?  → FLAGGED / R4. Stop.
  Does R5 fire?  → FLAGGED / R5. Stop.
  Does R6 fire?  → UNCERTAIN / R6. Stop.
  Does R7 fire?  → UNCERTAIN / R7. Stop.
  Does R8 fire?  → UNCERTAIN / R8. Stop.
  Does R9 fire?  → UNCERTAIN / R9. Stop.
  Does R10 fire? → UNCERTAIN / R10. Stop.
  None fired     → PASSED. Stop.
```

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

* `system_prompt.md` — the universal definition of a good field description, including the expected tone, length, format, and quality criteria
* `golden_examples.json` — a curated set of high-quality field descriptions used for few-shot grounding

This shared context is injected once per session. For each batch, the script then adds the relevant task instruction — `prompt_a_flagged_fields.md` or `prompt_b_uncertain_fields.md` — together with the field data for that batch.

Routing logic:

|Status|What happens|
|-|-|
|**FLAGGED**|Sent to the LLM with `prompt_a_flagged_fields.md` — if the description is missing, the LLM writes a new one from metadata; if the description exists but is unusable, the LLM replaces it|
|**UNCERTAIN**|Sent to the LLM with `prompt_b_uncertain_fields.md` — the LLM evaluates the existing description and suggests an improvement only if one is needed|
|**PASSED**|Not sent to the LLM — carried forward without change|
|**SKIPPED**|Not sent to the LLM — logged for visibility only and carried forward without change|

Fields are sent in batches of 50 per API call. Raw responses are written to `data/llm_response.json` before any further processing. This ensures that if anything fails downstream, the LLM output is not lost.

---

### Step 4 — Merge and Output

`01_ingest_classify_send.py`

Once all LLM responses are received and stored in `data/llm_response.json`, the script merges them with the original classified data from `data/sf_classified.json` and assembles a single Excel file for human review:

`review_queue_{timestamp}.xlsx`

The file contains three tabs:

|Tab|Contents|Reviewer action required|
|-|-|-|
|**Tab A — FLAGGED**|Original description + AI-written replacement|Approve, edit, or reject each row|
|**Tab B — UNCERTAIN**|Original description + AI-suggested revision|Approve, edit, or reject each row|
|**Tab C — PASSED / SKIPPED**|Original description only, no AI suggestion|No action required — included for full visibility|

The timestamp in the filename ensures that multiple runs do not overwrite each other, and every review file can be traced back to the exact run that produced it.

This file is a proposal, not an action.

---

### Step 5 — Human Review *(manual step)*

`data/review_queue_{timestamp}.xlsx`

The Admin opens `data/review_queue_{timestamp}.xlsx` and works through **Tab A** and **Tab B** — one row per field. For every row, the Admin enters one of three decisions in the **Approve / Edit / Reject** column:

|Decision|What it means|What happens next|
|-|-|-|
|**Approve**|The AI suggestion is accepted as written|Script 2 will write it to Salesforce exactly as shown|
|**Edit**|The AI suggestion needs adjustment|Admin writes the preferred description in the **Admin Version** column. Script 2 will use that text instead.|
|**Reject**|The AI suggestion is discarded|Script 2 skips this field. Nothing is written to Salesforce.|

> Every row in Tab A and Tab B must have a decision before Script 2 can run.
> Script 2 will not proceed if any decision is missing.

Once all rows have a decision, the Admin saves the file. The filename must not be changed — Script 2 identifies the correct file by its name and timestamp.

> \*\*Nothing in this step touches Salesforce. The review file is a proposal, not an action.\*\*

---

### Step 6 — Write-Back

`02_deploy_approved.py`

Script 2 begins with a validation pass before writing anything. It checks that:

* Every row in Tab A and Tab B has a value in the **Approve / Edit / Reject** column
* Every row marked **Edit** has a non-empty value in the **Admin Version** column
* No approved or edited description exceeds 255 characters — the Salesforce field limit

If any of these checks fail, the script stops and reports the problem. Nothing is written to Salesforce until the file passes validation in full.

Once validation passes, the script processes each row according to the Admin's decision:

|Decision|What Script 2 does|
|-|-|
|**Approve**|Writes the value from the **LLM Suggestion** column to Salesforce|
|**Edit**|Writes the value from the **Admin Version** column to Salesforce|
|**Reject**|Skips the field — no change is made|

Write-back is performed using the **Metadata API** via `02\_deploy_approved.py`. Each field is updated individually. If a single field update fails — for example due to a permissions issue or a locked field — the script logs the failure and continues processing the remaining fields. A partial failure does not stop the run.

Every field processed in this step is recorded in:

`data/write_log_{timestamp}.xlsx`

> This log is the audit trail for every change made to Salesforce. Keep it.

---

## The 10 Rule-Based Checks

The rules are listed in evaluation order. Rules 1–5 are evaluated in Step 1 and produce **FLAGGED**. Rules 6–10 are evaluated in Step 2 (only if Step 1 produced no match) and produce **UNCERTAIN**.

---

### Rule 1 — NULL / Blank

**Step 1 → FLAGGED**

The description is completely empty, or contains only whitespace.

The field has never been given a meaningful description. There is nothing for an AI system or developer to read. This is the highest-priority failure and is checked first.

---

### Rule 2 — Echo / Too Short

**Step 1 → FLAGGED**

The description repeats the field name, or contains so little content that it adds no information.

Examples: a field labelled `Customer Tier` with a description of `Customer Tier` or `Tier`. A description of three words or fewer with no substantive content. Any description that a developer could not act on without already knowing what the field does.

---

### Rule 3 — Wrong Type Hint

**Step 1 → FLAGGED**

The description explicitly contradicts the field's data type.

Examples: a Checkbox field described as *"Enter the customer's preferred contact method"* — a Checkbox stores true/false, not free text. A Number field described as *"Select from the dropdown"* — a Number field has no dropdown. The description leads any system reading it to the wrong conclusion about what the field can store.

---

### Rule 4 — Undefined Picklist

**Step 1 → FLAGGED**

The field is a Picklist or Multi-Select Picklist, but the description does not reference the values or explain what they represent.

Example: a Picklist field with values `Tier 1`, `Tier 2`, `Tier 3` and a description of *"Indicates the customer tier"*. Without knowing what each tier means, an AI cannot interpret the values correctly. The description must name the values or explain their significance.

---

### Rule 5 — Stale or Placeholder

**Step 1 → FLAGGED**

The description contains placeholder language, a work-in-progress marker, or an explicit signal that it is no longer current.

Examples: *"TBD"*, *"to be confirmed"*, *"ask John"*, *"deprecated"*, *"no longer used"*, *"TODO — confirm with legal"*. These may have been acceptable temporarily. In a production org read by Agentforce, they are direct misinformation — the AI will act on whatever text is present, including a statement that a field is deprecated when it is in active use.

---

### Rule 6 — Too Long

**Step 2 → UNCERTAIN**

The description exceeds 200 characters.

A description above this threshold is not necessarily wrong. It may be accurate, specific, and complete. However, Agentforce reads field descriptions at runtime as part of its context window. Shorter descriptions reduce token consumption and keep the metadata layer lean. The LLM is asked to evaluate whether the description can be meaningfully shortened without losing accuracy — not to replace it unconditionally.

Note: Salesforce enforces a hard limit of 255 characters for any field description. A description between 200 and 255 characters is technically valid but is a candidate for review under this rule.

---

### Rule 7 — Jargon Without Context

**Step 2 → UNCERTAIN**

The description uses internal acronyms, product-specific shorthand, or team-specific terms that are not explained.

Example: *"Used by the SFMC sync for BU segmentation"*. An AI agent — or a developer new to the org — cannot interpret `SFMC` or `BU` without prior knowledge. Internal shorthand creates silent knowledge gaps in the metadata layer.

---

### Rule 8 — Contradictory

**Step 2 → UNCERTAIN**

The description conflicts with something else observable in the field's metadata configuration.

Examples: a field described as *"Always required at case creation"* that is not marked as required in Salesforce. A Date field described as storing a date range. An Email field described as storing a comma-separated list of addresses. These contradictions are more subtle than a Wrong Type Hint (Rule 3) — the description does not obviously misname the type, but it implies a behaviour or structure the field cannot support.

---

### Rule 9 — Audience Mismatch

**Step 2 → UNCERTAIN**

The description is written for the end user filling in the form, rather than for the systems, integrations, and developers who read field metadata.

Examples: *"Click here to select the account type. Choose the option that best describes your customer."* Field descriptions are not help text or tooltips. They are consumed by Agentforce, integration layers, and developers. A description written as a UI instruction is in the wrong place and serving the wrong audience.

---

### Rule 10 — Ambiguous

**Step 2 → UNCERTAIN**

The description exists, passes all prior checks, and sounds plausible — but contains no specific information that would help a system or developer understand what the field actually stores.

Examples:

* *"Contains additional information about the source"*
* *"Used to categorize the record"*
* *"Stores relevant data for internal use"*

The ambiguity test: remove the field name and object name from the description. If what remains could describe any field in any system, it fails. A good description is specific enough to be meaningful without the field name for context.

This is the softest and hardest-to-catch failure. It requires understanding meaning, not just pattern-matching. That is why it is the last rule evaluated and why UNCERTAIN fields are sent to the LLM for judgment rather than flagged with certainty.

