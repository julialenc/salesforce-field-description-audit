# Project Handover — Salesforce Field Description Automation

Hi,

This note explains what the project does, how to get up to speed quickly, and exactly what to do next.

\---

## What the project is

A pipeline that audits Salesforce field descriptions at scale. It classifies descriptions by quality using rule-based checks, uses an LLM to generate suggested rewrites, presents them for human review in Excel, and writes approved changes back to Salesforce only after explicit Admin approval. Nothing touches Salesforce without a human decision.

The project is open-source, designed for Salesforce Developers and Architects, with the Salesforce Admin as the main operational user.

\---

## Fastest way to get up to speed

Read these two documents in this order — nothing else is needed to understand the project before you start:

1. **`README.md`** — what it does, the architecture, how to install and run it. Should take 10 minutes.
2. **`wiki/02\_how\_it\_works.md`** — the full pipeline logic: classification rules, LLM routing, Excel review format, write-back process. This is the most detailed document in the project. Read it before running anything.

The other wikis (01, 03, 04, 05) are reference material — you will need them as you go deeper, but they are not required before the first run.

\---

## Experiment first, MVP second — and why

The project is designed to be validated safely before it touches a real Salesforce org. The experiment uses synthetic data (288 training fields, 144 test fields — already in the `data/` folder) and a local LLM, so you can run and re-run it without credentials, without cost, and without any risk to a live org.

**For the experiment**, you can use either:

* **Ollama** — runs open-source models locally, fully offline, free
* **AOAI API Simulator** — simulates the Azure OpenAI API locally, no API key required

Both are called via HTTP, and the scripts support both out of the box. Use whichever is easier for you to set up.

The experiment has two phases — training set first, then test set. `wiki/03\_experiment\_and\_validation.md` explains the methodology in full, including the definition of done for each phase. Do not skip the training phase or go straight to the test set.

**For MVP against a real Salesforce org**, a company-approved LLM provider is required. My plan after the experiment passes is to use **Azure OpenAI**, which I use across my other projects. The configuration in `config.yml` would be:

```yaml
llm:
  provider: azure\_openai
  endpoint: https://MY-RESOURCE.openai.azure.com/
  model: gpt-4o        # my deployment name
  api\_key: MY\_AZURE\_API\_KEY
```

On model choice: `gpt-4o` is what I planned, but looking at my other projects, simpler models like `gpt-4o-mini` (or equivalent nano/haiku-tier models) may produce comparable output at significantly lower cost. I would suggest testing at least two models during the experiment phase and comparing the Admin approval rate between them before committing to one for MVP. The model is a one-line change in `config.yml` — it requires no code changes.

The `\_call\_azure\_openai()` function in Script 1 is already implemented and handles the Azure-specific URL format and authentication header. No code changes are needed to switch from experiment to Azure OpenAI.

\---

## Step-by-step: what to do

### 1\. Clone and install

```bash
git clone <repo-url>
cd salesforce-field-description-audit
pip install pyyaml requests openpyxl
```

### 2\. Create your local config

```bash
cp config.example.yml config.yml
```

Open `config.yml` and set:

* `mode: experiment`
* `data\_source.experiment\_file: data/sf\_metadata\_raw\_training.json`
* `llm.provider` to `ollama` or `aoai\_simulator` and the matching `endpoint`

Do not commit `config.yml` — it is in `.gitignore` for a reason. It will eventually contain real credentials.

### 3\. Set up a local LLM

Either:

* **Ollama**: install from https://ollama.com and run `ollama pull llama3` (or another model of your choice)
* **AOAI API Simulator**: follow setup at https://github.com/microsoft/aoai-api-simulator

### 4\. Run the experiment — Phase 1 (training set)

```bash
python scripts/01\_ingest\_classify\_send.py
```

This produces `data/sf\_classified.json`, `data/llm\_response.json`, and `data/review\_queue\_{timestamp}.xlsx`.

Open the review queue. Check `sf\_classified.json` first — verify the classifier is assigning the right status to the right fields (the expected status and rule are in the `\_expected\_status` and `\_expected\_rule` fields of the training JSON, so you can compare directly).

Then review Tab A and Tab B in the Excel file. Mark each row Approve / Edit / Reject.

```bash
python scripts/02\_deploy\_approved.py
```

This runs as a dry-run in experiment mode — no changes to Salesforce.

Iterate on the classifier logic and prompts until the Definition of Done in `wiki/03\_experiment\_and\_validation.md` is met.

### 5\. Run the experiment — Phase 2 (test set)

Switch in `config.yml`:

```yaml
data\_source:
  experiment\_file: data/sf\_metadata\_raw\_test.json
```

Run Scripts 1 and 2 again. Evaluate results against the same Definition of Done. Do not use the test set to tune anything — it is for validation only.

### 6\. MVP — switch to Azure OpenAI and real Salesforce

Once both experiment phases pass, update `config.yml`:

```yaml
mode: production

llm:
  provider: azure\_openai
  endpoint: https://MY-RESOURCE.openai.azure.com/
  model: gpt-4o
  api\_key: MY\_AZURE\_API\_KEY

salesforce:
  username: your\_username@example.com
  password: YOUR\_PASSWORD
  security\_token: YOUR\_SECURITY\_TOKEN
  domain: login
```

The Salesforce connectivity (Tooling API ingestion and Metadata API write-back) is stubbed in the scripts with `NotImplementedError` and detailed implementation guidance in the docstrings. These are the two remaining pieces of code to implement before MVP.

\---

## Current status

All files are in place:

* `data/` — synthetic training and test datasets (ready to use)
* `prompts/` — all five prompt files (system prompt, golden examples, Prompt A, B, C)
* `scripts/` — both scripts, fully implemented for experiment mode
* `wiki/` — all five wiki files, up to date
* `config.example.yml` — template with full documentation
* `requirements.txt` — minimal and accurate

The project has not been run end to end yet. The first run of Script 1 is the next step.

Good luck — the design is documented in detail, and the wikis should answer most questions before you need to ask them.

