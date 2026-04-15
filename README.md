# Salesforce Field Description Automation

Salesforce field descriptions are often **missing, vague, or outdated**. In AI-enabled orgs, this is no longer just a documentation problem, but a systems problem.

AI agents such as Agentforce read **metadata**. When descriptions are blank, vague or stale, AI guesses and may mistinterpret them or even act on the wrong meaning. In large orgs, this creates avoidable risk across implementation, support, and governance.

This project is an **open-source, human-supervised pipeline for improving Salesforce field descriptions at scale**. It extracts field metadata, classifies description quality, uses an LLM to generate proposed rewrites, presents them for human review, and writes back only what has been explicitly approved.

Built for **Salesforce Developers and Architects**, it gives teams a reusable solution instead of building this workflow from scratch. The main operational **beneficiary is the Salesforce Admin**, who remains the final quality gate.

---

## Features

- **Extract field metadata** via the **Tooling API**, with experiment mode supported through a synthetic input file.
- **Classify description quality** with 10 rule-based checks that assign `FLAGGED`, `UNCERTAIN`, `PASSED`, or `SKIPPED`.
- **Generate LLM-assisted rewrites** using shared prompt context plus task-specific prompts for `FLAGGED` and `UNCERTAIN` fields.
- **Require human review**: every proposed change must be **approved, edited, or rejected** before deployment.
- **Write back safely** through a separate deployment script that validates decisions before calling the **Metadata API**.
- **Support experiment, MVP, and production** through the same pipeline, with configurable seams for data source, LLM provider, write-back mode, and runtime interface.
- **Preserve audit artifacts** including `sf_classified.json`, `llm_response.json`, `review_queue_{timestamp}.xlsx`, and `write_log_{timestamp}.xlsx`.

---

## Why This Is Better Than Runtime Guessing

When field descriptions are missing, Agentforce may still infer meaning — but it does so **at runtime**, inside a live workflow.

This project moves that inference **upstream** into a controlled metadata cleanup process. It uses structured field metadata to generate a **proposed description**, exposes that proposal to **human review**, and writes back only what has been explicitly approved.

The result is not a temporary workaround for one interaction, but a durable metadata improvement for the whole org. The advantage is not that the LLM never infers; it is that inference happens in a **safer place**, with **more structure**, and under **human control**.

---

## High-Level Architecture

<pre>
[0] Salesforce metadata
 - Experiment: `data/sf_metadata_raw.json`
 - MVP & Production: Tooling API
        ↓
[1] Script 1                                        # ingests data, classifies fields, routes to LLM, saves LLM response
        ↓
`data/sf_classified.json`                           # fields classified by description quality (`wiki/02_how_it_works.md`)
        ↓
 Shared prompt context                              # universal rules for field description + curated examples
`system_prompt.md` + `golden_examples.json`
        ↓
FLAGGED   → Prompt A → LLM                          # fields with missing description or clear description failure
UNCERTAIN → Prompt B → LLM                          # fields with possible description failure
PASSED / SKIPPED → no LLM                           # fields meeting all criteria or system fields 
        ↓
`data/llm_response.json`                            # LLM suggestion for descriptions
        ↓
`data/review_queue_{timestamp}.xlsx`                # file for Admin review
        ↓
Human review — approval gate                        # Admin approves, edits or rejects LLM suggestions
        ↓
[2] Script 2                                        # writes Admin-approved descriptions to Salesforce
        ↓
 - Experiment: dry-run
 - Live: Metadata API write-back
        ↓
`data/write_log_{timestamp}.xlsx`
</pre>

**Script 1** prepares proposals, **human review** is the approval gate, and **Script 2** is the only stage that can trigger live write-back.

For step-by-step workflow, see `wiki/02_how_it_works.md`. For the full architectural view, see `wiki/05_architecture_and_reproducibility.md`.
