# Project Overview

## What This Project Does

Salesforce fields carry a description — a short text explaining what a field
stores and what it means. In most orgs, these descriptions are in poor shape.

This tool addresses three specific problems:

- **Missing descriptions** — fields have no description at all, leaving admins,
  developers, and AI systems without context
- **Ambiguous descriptions** — descriptions exist but are too vague to be useful
  without UI context (e.g., "used for reporting")
- **Stale descriptions** — descriptions no longer match the actual usage of the
  field after years of org evolution

It extracts field metadata from a Salesforce org, classifies every field
description by quality, uses an LLM to generate suggested rewrites, presents
results to a human reviewer, and writes approved changes back to Salesforce.

This tool is a **human-supervised automation pipeline, not an autonomous agent**.
It prepares suggestions and waits. It cannot act unless a human opens a spreadsheet,
makes a decision (approve / edit / reject) row by row, and explicitly triggers the write-back script.

Nothing is written to Salesforce without explicit human approval.

---

## Why This Matters Now

Salesforce Agentforce does not ask humans what a field means.
It reads the description.

- When a field description is missing, the **AI guesses.**

- When it is vague, the **AI misinterprets.**

- When it contradicts the actual field configuration, the **AI acts on wrong information.**

This is not a cosmetic problem. Poor metadata causes wrong answers, wrong actions,
and support escalations in AI-powered orgs.

Most Salesforce orgs have accumulated years of undocumented fields.
This tool makes the cleanup systematic, reviewable, and repeatable.

---

## Human Control by Design

This tool is **a supervised automation pipeline, not an autonomous agent.**
It prepares suggestions and waits. It cannot act on its own.

The only change it can make to Salesforce is updating the description text
of existing fields. It cannot delete fields, hide fields, or alter field
configuration of any kind.

The admin opens the review file, decides row by row — approve, edit, or reject —
and manually triggers the write-back script. Nothing reaches Salesforce before that.

---

## Who This Is For

This project is designed to be **org-agnostic and easily adaptable**.

The objects to scan, the LLM provider, and the authentication method are all
configured in a single `config.example.yml` file. No Python knowledge is
required to point the tool at a different org or a different object list.

Intended users:
- Salesforce Admins preparing an org for Agentforce or Data Cloud
- Salesforce Architects doing pre-implementation metadata audits
- Developers who want to adapt or extend the pipeline

---

## Repository Structure

```
├── data/
│   ├── sf_metadata_raw.json         # Raw field metadata — in production, extracted from Salesforce; in experiment mode, loaded from this file
│   ├── sf_classified.json           # Classifier output — each field labelled FLAGGED, UNCERTAIN, PASSED, or SKIPPED. Committed as experiment reference only
│   ├── llm_response.json            # Raw LLM suggestions before human review. Committed as experiment reference only
│   └── review_queue_{timestamp}.xlsx  # Generated review file — one row per field, three tabs. Committed as experiment reference only
├── prompts/
│   ├── system_prompt.md             # Quality criteria and instructions — injected once per session
│   ├── golden_examples.json         # Hand-picked perfect field descriptions used for few-shot grounding
│   ├── prompt_a_flagged_fields.md   # Instruction for FLAGGED fields — clear quality failures
│   └── prompt_b_uncertain_fields.md # Instruction for UNCERTAIN fields — borderline cases
├── scripts/
│   ├── 01_ingest_classify_send.py   # Extract from Salesforce, classify, call LLM, produce review file
│   └── 02_deploy_approved.py        # Read human approvals, write approved descriptions back to Salesforce
├── wiki/
│   ├── 01_project_overview.md
│   ├── 02_how_it_works.md
│   ├── 03_experiment_and_validation.md
│   ├── 04_human_review_process.md
│   └── 05_architecture_and_reproducibility.md
├── .gitignore
├── README.md
├── config.example.yml               # Copy, rename to config.yml, fill in credentials and object list before running
└── requirements.txt
```



