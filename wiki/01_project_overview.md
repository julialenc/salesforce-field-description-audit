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

An AI agent does not ask a colleague what a field means. It reads the metadata. When a field description is missing, it has the API name and nothing more; when it is vague, it misreads the field; when it contradicts the field's configuration, it acts on wrong information. Most Salesforce orgs have years of undocumented fields. This tool makes the cleanup systematic, reviewable and repeatable.

### Salesforce AI Products in 2026

Salesforce renamed much of its AI line-up during 2025 and 2026, and many Admins and Architects find the names hard to follow. What they have in common: each reads the same object and field metadata this tool improves.

| Name (checked 10 November 2026) | Since | What it is | Why field descriptions matter to it |
|---|---|---|---|
| **Agentforce** (launched as Agentforce 360) | October 2025 | Salesforce's own agents: service, sales, the Coworker assistant, custom agents | They choose fields and actions by reading object and field descriptions |
| **Data 360** (formerly Data Cloud) | October 2025 | The data layer that gives agents business context. Same product, new name | Context is only as clear as the fields it is built from |
| **Headless 360** (now listed as Headless Toolkit) | April 2026 | Salesforce capabilities offered as APIs, MCP tools and CLI commands, so agents can work without the browser | Outside agents and coding tools (Claude, ChatGPT, Cursor, Codex) read the org's schema, descriptions included |
| **AIforce**, with **Claudeforce** and **Slackforce** | August–September 2026 | Salesforce data and actions inside Claude and Slack, under the org's existing permissions | An answer about a deal in Claude or Slack is built on the same field metadata |

The core clouds were renamed after Agentforce in 2025 ("Agentforce Sales", "Agentforce Service"). Salesforce's product pages call them Sales Cloud and Service Cloud again (checked 10 November 2026), while the Winter '27 release notes, written in August, still use the Agentforce names. Expect to meet both for a while.

Whether a given agent or integration actually uses the description depends on how it retrieves metadata. Salesforce's Trailhead unit on agent access says that a blank field description "returns the developer API name and nothing else" through its MCP Describe tool.

Sources: Salesforce's announcements of [Headless 360](https://www.salesforce.com/news/stories/salesforce-headless-360-announcement/) and [Claudeforce](https://www.salesforce.com/news/press-releases/2026/08/26/salesforce-and-anthropic-announce-claudeforce/), its [Dreamforce 2026 summary](https://www.salesforce.com/blog/dreamforce-2026-announcements/), its [Data 360 guide](https://www.salesforce.com/data/guide/), its [products page](https://www.salesforce.com/products/), and the Trailhead unit [Prepare Your Data for Headless Functionality](https://trailhead.salesforce.com/content/learn/modules/data-foundation-for-headless-functionality/prepare-your-data-for-headless-functionality).

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
│   ├── sf_metadata_raw_training.json  # Synthetic training set — 288 fields across 4 objects, used during classifier development and prompt iteration
│   ├── sf_metadata_raw_test.json      # Synthetic test set — 144 fields across 4 objects, held out for final validation only
│   ├── org_context_synthetic.md       # Example org context file for the synthetic org (glossary, systems, teams, conventions)
│   ├── review_evidence/               # The four reviewed 40-field samples behind the reported approval rates, with a README
│   └── sample/                        # Outputs of one real run, for reference (249 fields read from a Developer Edition org, Azure gpt-5.4-mini)
│       ├── sf_classified_sample.json  # Classifier output — each field labelled FLAGGED, UNCERTAIN, REVIEWED, or SKIPPED
│       ├── llm_response_sample.json   # LLM suggestions with Unverified and Missing, before review
│       ├── review_queue_sample.xlsx   # The review file — Tab A (FLAGGED), Tab B (UNCERTAIN + proposed rewrites), Tab C (reference)
│       └── write_log_sample.xlsx      # Script 2's audit log from the write-back test: SUCCESS, UNCHANGED, SKIPPED, FAILED
│   # Each run writes sf_classified.json, llm_response.json, review_queue_<timestamp>.xlsx,
│   # approved_descriptions_<timestamp>.csv and write_log_<timestamp>.xlsx into data/ (not committed)
├── prompts/
│   ├── system_prompt.md               # Quality criteria and instructions — injected once per session for all LLM calls
│   ├── golden_examples.json           # High-quality descriptions of invented fields (in neither dataset) used for few-shot grounding
│   ├── prompt_a_flagged_fields.md     # Task instruction for FLAGGED fields — clear quality failures (Rules 1–5)
│   ├── prompt_b_uncertain_fields.md   # Task instruction for UNCERTAIN fields — borderline cases requiring LLM judgment (Rules 6–9)
│   └── prompt_c_reviewed_fields.md    # Task instruction for REVIEWED fields — passed all rules; LLM keeps unless clearly inadequate
├── scripts/                           # numbered in run order: 00 prepare → 01–02 process → 03 check
│   ├── 00_check_setup.py              # Prepare: check Python, packages, config, LLM connection and Salesforce CLI login, with a fix per failure
│   ├── 00_a_seed_demo_org.py          # Prepare (demo org only): create the training set's custom fields in a Developer Edition org; reset them
│   ├── 00_b_check_org_parity.py       # Prepare (demo org only): check that reading from the org gives the same input as the training file
│   ├── 01_ingest_classify_send.py     # Process: read fields (synthetic file or org), classify, call the LLM, produce the review file
│   ├── 02_deploy_approved.py          # Process: validate the Admin's decisions; dry run, CSV export or deploy to the org
│   ├── 03_a_evaluate_suggestions.py   # Check (optional): automatic quality check of LLM suggestions, pass rate per prompt and rule
│   ├── 03_b_review_sample.py          # Check (optional): draw a 40-field review sample from a review file, re-review it after a change, score it
│   ├── 03_c_validate_classifier.py    # Check (optional): compare classifier output with the dataset labels; list every mismatch
│   └── sf_cli.py                      # Helper imported by the scripts (Salesforce CLI calls, read-only metadata retrieve); not run on its own
├── tests/
│   ├── test_classifier.py             # Unit tests for the R1–R9 rules and the known classifier fixes
│   ├── test_cache.py                  # Unit tests for the cache key
│   ├── test_context.py                # Unit tests for neighbour fields, extra metadata and the org context file
│   └── test_evaluate.py               # Unit tests for the suggestion checker
├── wiki/
│   ├── 01_project_overview.md
│   ├── 02_how_it_works.md
│   ├── 03_experiment_and_validation.md
│   ├── 04_human_review_process.md
│   ├── 05_architecture_and_reproducibility.md
│   └── 06_lessons_learned.md          # What building and testing the pipeline taught, for anyone building a similar system
├── .gitignore
├── CONTRIBUTING.md                    # How to change the code safely and check a change
├── LICENSE
├── NOTICE
├── README.md
├── ROADMAP.md                         # What is left, most important first
├── config.example.yml                 # Copy to config.yml and fill in PART 1 (the LLM settings)
└── requirements.txt
```
