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

Nothing is written to Salesforce without explicit human approval.

---

## Why This Matters Now

Salesforce Agentforce does not ask humans what a field means.
It reads the description.

When a field description is missing, the AI guesses.
When it is vague, the AI misinterprets.
When it contradicts the actual field configuration, the AI acts on wrong information.

This is not a cosmetic problem. Poor metadata causes wrong answers, wrong actions,
and support escalations in AI-powered orgs.

Most Salesforce orgs have accumulated years of undocumented fields.
This tool makes the cleanup systematic, reviewable, and repeatable.

---

## What This Tool Does Not Do

- It does not write anything to Salesforce automatically
- It does not make decisions without a human in the loop
- It does not require the reviewer to write descriptions from scratch
- It does not overwrite previous output files when run again

The human reviewer reads, judges, and approves. The tool does the rest.

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
│   ├── mock_fields.json        # Synthetic input — safe to share publicly
│   ├── mock_fields.xlsx        # Human-readable version of the same input
│   └── sample_output.xlsx      # Example of what the final review file looks like
├── prompts/
│   ├── grounding_universal.txt        # Shared context injected into every prompt
│   ├── prompt_a_flagged_fields.txt    # For fields with clear quality failures
│   └── prompt_b_uncertain_fields.txt  # For fields that may or may not be acceptable
├── scripts/
│   ├── 01_ingest_classify_send.py     # Extract, classify, call LLM, produce review file
│   └── 02_deploy_approved.py          # Read approvals, write to Salesforce
├── wiki/
│   ├── 01_project_overview.md
│   ├── 02_how_it_works.md
│   ├── 03_experiment_and_validation.md
│   ├── 04_human_review_process.md
│   └── 05_architecture_and_reproducibility.md
├── .gitignore
├── README.md
├── config.example.yml                 # Copy, rename to config.yml, edit before running
└── requirements.txt
```



