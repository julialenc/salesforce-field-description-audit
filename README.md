# !!! THIS IS WORK IN PROGRESS - DO NOT USE !!! 

# Salesforce Field Description Automation

Salesforce field descriptions are often **missing, vague, or outdated**. In AI-enabled orgs, this is no longer just a documentation problem, but a systems problem.

AI agents such as Agentforce read **metadata**. When descriptions are blank, vague or stale, AI guesses and may mistinterpret them or even act on the wrong meaning. In large orgs, this creates avoidable risk across implementation, support, and governance.

This project is an **open-source, human-supervised pipeline for improving Salesforce field descriptions at scale**. It extracts field metadata, classifies description quality, uses an LLM to generate proposed rewrites, presents them for human review, and writes back only what has been explicitly approved.

Built for **Salesforce Developers and Architects**, it gives teams a reusable solution instead of building this workflow from scratch. The main operational **beneficiary is the Salesforce Admin**, who remains the final quality gate.

---

## Features

- **Extract field metadata** via the **Tooling API**, with experiment mode supported through synthetic input files.
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
 - Experiment: `data/sf_metadata_raw_training.json` (development)
               `data/sf_metadata_raw_test.json`     (final validation)
 - MVP & Production: Tooling API
        ↓
[1] Script 1                                        # ingests data, classifies fields, routes to LLM, saves LLM response
        ↓
`data/sf_classified.json`                           # fields classified by description quality (`wiki/02_how_it_works.md`)
        ↓
 Shared prompt context                              # universal rules for field description + curated examples
`system_prompt.md` + `golden_examples.json`
        ↓
FLAGGED   → Prompt A → LLM                          # fields with missing description or clear description failure (R1-R5)
UNCERTAIN → Prompt B → LLM                          # fields with possible description failure (R6-R10)
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

---

> **Current status:** the first-run setup flow is being finalized now. The configuration structure and installation steps are defined, but the full end-to-end first run has not yet been executed on the current codebase. This section will be updated after Script 1 has been tested successfully.

## Installation

### Prerequisites

- **Python 3.10+**
- **Git**
- Dependencies from `requirements.txt`
- For **experiment mode**: one local LLM option
  - **AOAI API Simulator**, or
  - **Ollama**

### Install

Clone the repository and install dependencies:

```bash
git clone <your-repo-url>
cd salesforce-field-description-audit
pip install -r requirements.txt
```

Create your local config file from the template:

```bash
cp config.example.yml config.yml
```

Then open `config.yml` and fill in your own values.

### First-Run Preparation

Before running the scripts:
- set `mode: experiment`
- set `data_source.experiment_file` to `data/sf_metadata_raw_training.json` to start with the training set
- choose an LLM provider in the `llm` block
- keep `config.yml` local only and never commit it

See `wiki/03_experiment_and_validation.md` for the full two-phase experiment methodology, including when to switch to the test set.

---

## Quick Start

The simplest way to try the project is in **experiment mode** using the training set.

### 1. Create your local config

Copy `config.example.yml` to `config.yml`:

```bash
cp config.example.yml config.yml
```
Then update `config.yml` so that:

- `mode: experiment`
- `data_source.experiment_file` points to `data/sf_metadata_raw_training.json`
- `llm.provider` is set to your local or simulated provider

### 2. Run Script 1

```bash
python scripts/01_ingest_classify_send.py
```

Expected outputs:

- `data/sf_classified.json`
- `data/llm_response.json`
- `data/review_queue_{timestamp}.xlsx`

### 3. Review the spreadsheet

Open:

`data/review_queue_{timestamp}.xlsx`

Review Tab A and Tab B, then mark each row as:

- Approve
- Edit
- Reject

Save the file without renaming it.

### 4. Run Script 2

```bash
python scripts/02_deploy_approved.py
```

In **experiment mode**, Script 2 runs as a **dry-run**:

- it validates the review file
- it records the results
- it does not write anything to Salesforce

Expected output:

`data/write_log_{timestamp}.xlsx`

### 5. Read more

For the full workflow, see:

`wiki/02_how_it_works.md`
`wiki/03_experiment_and_validation.md`
`wiki/04_human_review_process.md`

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Language | **Python 3.10+** | Core pipeline logic and scripting |
| Metadata ingestion | **Salesforce Tooling API** | Reads field metadata in MVP and production |
| Write-back | **Salesforce Metadata API** | Writes approved field descriptions back to Salesforce |
| Review interface | **Excel (`.xlsx`)** | Human review artifact for Approve / Edit / Reject decisions |
| Configuration | **YAML** (`config.example.yml` → `config.yml`) | Controls mode, data source, provider settings, and object scope |
| Experiment input | **`data/sf_metadata_raw_training.json`** (288 fields) and **`data/sf_metadata_raw_test.json`** (144 fields) | Synthetic metadata datasets for safe experiment-mode runs — training set for development, test set for final validation |
| LLM providers | **AOAI API Simulator, Ollama, Azure OpenAI, OpenAI-compatible APIs, Amazon Bedrock, Google Vertex AI** | Generates proposed field-description rewrites depending on runtime mode |
| Prompt assets | **Markdown + JSON** (`system_prompt.md`, `golden_examples.json`, prompt templates) | Defines quality rules, examples, and task-specific instructions |
| Artifacts | **JSON + Excel** | Stores classification output, raw LLM output, review queue, and write log |

For operating stages, architecture, and provider seams, see `wiki/05_architecture_and_reproducibility.md`.

---

## Documentation

Detailed documentation lives in the `wiki/` folder:

- `wiki/01_project_overview.md` — problem statement, why it matters, and who the project is for
- `wiki/02_how_it_works.md` — step-by-step pipeline logic, classifier routing, LLM flow, and write-back process
- `wiki/03_experiment_and_validation.md` — two-phase experiment methodology (training and test sets), validation approach, and definition of done
- `wiki/04_human_review_process.md` — Admin workflow for reviewing, approving, editing, or rejecting suggestions
- `wiki/05_architecture_and_reproducibility.md` — architecture, operating stages, reproducibility, safety, and future evolution

Use the README as the entry point and the wiki for deeper detail.

---

## Who This Is For

This project is primarily for **Salesforce Developers and Architects** who want a reusable, production-minded way to improve field descriptions at scale instead of building a workflow from scratch.

Typical users include:

- **Developers and Architects evaluating the repo**  
  They discover the project on GitHub, want to understand the setup quickly, and usually start in **experiment mode** with the training set.

- **Learners, contributors, and experimenters**  
  They want to test the classifier, prompts, and review flow without needing Salesforce credentials, using the synthetic datasets in **experiment mode**.

- **Real implementers testing on a Salesforce org**  
  They often begin in experiment mode, then switch to live metadata ingestion and real LLM calls in **MVP mode**.

The main operational **beneficiary** is the **Salesforce Admin**, who reviews the spreadsheet and remains the final approval gate before anything is written back to Salesforce.

Tech Consultants, Data Cloud specialists, and Agentforce advisors may also use the project as a structured way to assess and improve metadata readiness.

---

## Contributing

Contributions are welcome.

Contribution guidelines are being finalized and will be added in `CONTRIBUTING.md`.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
