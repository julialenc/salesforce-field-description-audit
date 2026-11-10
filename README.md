# Salesforce Field Description Automation

**In 2026 Salesforce opened the org to AI agents. Your field descriptions are now part of the interface they use.**

Agentforce works inside the org. Since Headless 360, every Salesforce capability is also an API, an MCP tool or a CLI command, so Claude, ChatGPT and coding agents such as Cursor and Codex work on the same org from outside, and Claudeforce and Slackforce bring Salesforce data and actions into Claude and Slack. Whatever the entry point, an agent that meets a field reads its metadata to understand it. If the description is blank, Salesforce's own Trailhead guidance is blunt: the agent gets "the developer API name and nothing else". It cannot ask a colleague what `Flag__c` means. It guesses, and then acts on the guess.

Most orgs carry years of fields that nobody described, or described as "used for tracking". Until now that was a documentation gap. In an agentic org it is a reliability risk, and it grows with every agent you connect. It is also one of the few AI-readiness investments that does not depend on a product roadmap: Salesforce's product names have changed several times since 2025 ([wiki 01](wiki/01_project_overview.md#salesforce-ai-products-in-2026) maps them), but a description fixed once serves every agent and integration that reads field descriptions, under whatever name comes next.

**This open-source tool turns that cleanup into a controlled, repeatable audit.** It checks the description of every custom field on the objects you choose, drafts a better one with an LLM, and puts each suggestion in an Excel workbook where the Admin approves, edits or rejects it. What the model could not confirm is flagged, not hidden; only approved text is used, and by default it goes to a CSV for your release process, not straight into Salesforce. On synthetic fields the prompts had never seen, 12 of 20 suggestions were ready as written and 6 more needed one fact only the business has.

The same workbook earns its keep without any agent project: when you take over an org, rework a heavily customized object, or prepare a design session, it is the list of what the org never wrote down, turned into specific questions for the people who know the answers.

> **Status (November 2026): v0.1, works end to end, tested on synthetic data only.**
>
> - **Tested:** the whole cycle on synthetic fields (a fictional outdoor-equipment retailer): reading the fields from a free Developer Edition org, drafting suggestions, reviewing them in Excel, exporting them to CSV and deploying them back to the org.
> - **Not tested:** a real organization's metadata. That pilot is handed over; [ROADMAP.md](ROADMAP.md), item 1, describes it for whoever takes the project on: a Salesforce Admin or Architect working with an NGO or a small business.
> - Prompt and classifier tuning is closed. The project is looking for a maintainer.

---

## What You Review

"Description" here means the **Description** of a field in **Setup → Object Manager → [object] → Fields & Relationships → [field]**. It is not the Help Text, which users see on the record page; the tool reads Help Text as extra context but never changes it.

Script 1 produces an Excel workbook. Two real rows from a run on the Developer Edition org (the suggestions were written by Azure gpt-5.4-mini; the org context file is a short glossary the Admin writes once):

| Object.Field | Current description | Suggestion | Missing (questions for the field owner) | Admin decision |
|---|---|---|---|---|
| `Account.Customer_Grade__c` (Picklist: A, B, C, D) | Grade assigned to the customer based on their value and engagement. | Customer grade band based on last 12 months' net revenue and engagement score, recalculated quarterly. Values: A (top 10%), B (next 20%), C (next 40%), D (rest and new customers). A is best. | — (the meanings came from the org context file) | **Approve** |
| `Contact.Flag__c` (Checkbox) | Used internally for tracking. | General flag for this record. | What does checked mean? | **Edit**. `Admin_Version`: *"Checked when the contact has agreed to be a reference customer for sales calls. Set by the account manager; read by the reference-request list view."* |

The `Admin_Version` in the second row is illustrative: the synthetic org has no field owner to ask, so the answer was written for this example. It shows what the human adds. The LLM could only say "a flag"; the field owner knows what checked means, who sets it and what reads it.

That row is the common case. A blank description is easy to spot; a checkbox called `Flag__c` that "is used for tracking" is not. The workbook flags it and turns it into a concrete question for the field owner. It also surfaces what the model may have assumed: claims it could not confirm from the input are listed under **Unverified**, facts it would need under **Missing**. The suggestion is still a draft. In the test on unseen fields, 2 of 20 suggestions had a wrong or lost fact, and the review is where those are caught.

What the tool cannot do is check a claim against your automation, or tell you which systems depend on a field. If a suggestion says "set by a flow after approval", someone still has to trace the flow, Apex or integration mapping. A clear description tells you what to investigate; it does not establish it.

In a design or integration project, the same rows become meeting preparation: for `Customer_Grade__c`, ask who owns the grade definition, what recalculates it and where the quarterly schedule is documented. The answers are decisions to record.

You can open the full workbook from that run before installing anything: [`data/sample/review_queue_sample.xlsx`](data/sample/review_queue_sample.xlsx) (249 fields), with the write log of the write-back test in [`data/sample/write_log_sample.xlsx`](data/sample/write_log_sample.xlsx).

---

## What It Does

1. **Reads** the fields of the objects you list (`objects` in `config.yml`; Account, Contact, Opportunity and Case by default) from a sandbox or Developer Edition org through the Salesforce CLI, or from a synthetic file for a first try. Custom fields only, unless you include standard fields.
2. **Checks** every description against nine rules: missing, too short or just the field name, wrong for the field type (a checkbox described as a text box), a picklist that never names its values, a placeholder such as "TBD", too long, unexplained abbreviations, and a few more ([wiki 02](wiki/02_how_it_works.md)).
3. **Drafts** a suggestion with an LLM: a rewrite where a check failed; for a field that **passed the automated checks**, the LLM keeps the description unless it is clearly inadequate. (In the workbook and the docs this status is called `REVIEWED`; it means "passed the automated checks", not "reviewed by a person".)
4. **Produces the workbook** for the Admin: Tab A for clear failures, Tab B for possible issues and proposed rewrites, Tab C for reference.
5. **Uses only what the Admin approved:** the Admin's own text for Edit, the suggestion for Approve. By default the approved descriptions go to a **CSV file** for your team's release process; deploying them to the org is a separate, explicit setting.

---

## Before You Start: Scope and Access

Points to agree with whoever manages access to the org:

- **Which fields.** The objects you list in `config.yml`, custom fields only by default.
- **What goes to the LLM.** For each field: API name, type, current description, picklist values, formula, lookup target, and label, help text, length and decimal places where set; plus the org context file if you write one. No record data is read or sent. Use an LLM provider your organization approves for this metadata (for example Azure OpenAI); the tool refuses free-tier providers when it reads from an org.
- **Salesforce access.** Tested with one account only: a **System Administrator in a Developer Edition org**. Reading is a metadata retrieve (Metadata API through the Salesforce CLI); deploying uses the same API to change the field descriptions. **The minimum permissions for retrieving and for deploying have not been tested separately.** Salesforce documents Metadata API access as needing API Enabled plus a metadata permission such as "Modify Metadata Through Metadata API Functions"; treat that as a starting point to verify with your Salesforce administrator, not as a tested access request. A read-only audit with CSV export needs no deploy rights at all.
- **Where to run it.** A sandbox or a Developer Edition. Never start on production.
- **Writing back.** `write_back: export` (the default) only writes a CSV. `write_back: deploy` changes the Description of each approved field and nothing else, and asks you to type the org alias before it starts. Every row ends up in a write log.

---

## Quick Start (about 10 minutes, no Salesforce needed)

You need **Python 3.10+**, **Git** and an LLM API key: **Cerebras** (free trial with the open-weight gpt-oss-120b; key at https://cloud.cerebras.ai, needs a verified payment method) or **Azure OpenAI** (paid).

**1. Install** (Windows, CMD):

```
git clone https://github.com/julialenc/salesforce-field-description-audit.git
cd salesforce-field-description-audit
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yml config.yml
```

macOS / Linux: the same with `source venv/bin/activate` and `cp config.example.yml config.yml`.

**2. Configure.** Open `config.yml` and fill in PART 1: `llm.api_key`, plus `endpoint` and `model` if you don't use Cerebras. Everything else has a working default: the synthetic training set as input and a CSV export as output. Keep `config.yml` on your machine; never commit it.

**3. Check the setup:** `python scripts/check_setup.py` checks Python, packages, config, the input file and the LLM connection, and says how to fix anything that fails.

**4. Run Script 1:** `python scripts/01_ingest_classify_send.py` checks 288 synthetic fields, sends 271 to the LLM and writes `data/review_queue_<timestamp>.xlsx` (about 12 minutes on Cerebras).

**5. Review the workbook.** In Tab A and Tab B, read the current description, the suggestion and the Unverified and Missing columns. Choose **Approve**, **Edit** (type the final text in `Admin_Version`) or **Reject**. Save the file without renaming it. Reviewing someone else's run needs only this step: the workbook and knowledge of the fields.

**6. Run Script 2:** `python scripts/02_deploy_approved.py` checks that every row has a decision, then writes the approved text to `data/approved_descriptions_<timestamp>.csv` and an audit log to `data/write_log_<timestamp>.xlsx`. Nothing is written to Salesforce.

### On a Salesforce org

1. A free Developer Edition (https://developer.salesforce.com/signup) or a sandbox, and the Salesforce CLI (the Windows installer at https://developer.salesforce.com/tools/salesforcecli is faster than npm). Log in once: `sf org login web --alias sfdesc-dev`
2. For a demo: `python scripts/seed_demo_org.py validate`, then `deploy`, creates the training set's 231 custom fields with their deliberately messy descriptions; `reset` puts them back after a test
3. In `config.yml`: `source: org`, `salesforce.target_org: <your alias>`, the `objects` to audit, and an approved LLM provider. Keep `write_back: export` for the audit; set `deploy` only when you decide to write to the org
4. Run `check_setup.py`, Script 1, review, Script 2 as above

---

## From Approved Text to a Release

The CSV is the hand-off to whoever owns your metadata. One approved row from a run:

```
Object,Field_API_Name,Decision,Old_Description,New_Description
Account,Customer_Grade__c,Approve,Grade assigned to the customer based on their value and engagement.,"Customer grade band based on last 12 months' net revenue and engagement score, recalculated quarterly. Values: A (top 10%), B (next 20%), C (next 40%), D (rest and new customers). A is best."
```

**If your team keeps metadata in Git** (Salesforce DX source format), a developer or release engineer copies `New_Description` into the field's file, `force-app/main/default/objects/Account/fields/Customer_Grade__c.field-meta.xml`, and opens a pull request. The diff is one line:

```diff
-    <description>Grade assigned to the customer based on their value and engagement.</description>
+    <description>Customer grade band based on last 12 months' net revenue and engagement score, recalculated quarterly. Values: A (top 10%), B (next 20%), C (next 40%), D (rest and new customers). A is best.</description>
```

Who reviews it is your team's rule; a sensible default is the field owner for the meaning and the release owner for the deployment. The tool does not write to your repository: that step, and the pull request, stay with your team.

**If there is no source control** for this metadata, the Admin can apply the CSV in Setup, or use `write_back: deploy` against a sandbox. A deploy is not all-or-nothing: some fields can succeed while others fail (for example a field deleted since the workbook was made). Each row's result, SUCCESS or FAILED with the reason, is in `data/write_log_<timestamp>.xlsx`; check it after every deploy.

---

## Results

Measured on synthetic data with the recommended setup (Azure gpt-5.4-mini, reasoning effort medium, an org context file). Full method and numbers: [wiki 03](wiki/03_experiment_and_validation.md).

| Measure | Training set (288 fields) | Test set (144 fields the prompts never saw, run once) |
|---|---|---|
| Checks give the expected result | 279/288 (96.9%) | 128/144 (88.9%) |
| Suggestions for failed fields that pass the automatic quality check | 88% | 87% |
| Suggestions for failed fields usable as written (20-field sample) | 16/20 (80%) | 12/20 (60%) |

On the unseen fields, 12 of 20 suggestions were ready as written, 6 were correct but waited for one fact only the business has (what a checkbox means, what a tier stands for), and 2 had a wrong or lost fact that the review caught. The org context file had been written for the training fields and covered the new ones less well. **Write an org context file for the objects you audit**; it was the largest single improvement in the experiment.

The samples were reviewed against a written Approve / Edit / Reject rubric with an AI assistant, not by an independent Salesforce Admin. Treat 12 of 20 as a reason to run a pilot, not as a basis for estimating effort in your org: [ROADMAP.md](ROADMAP.md), item 1, lists what to measure in one.

**Cost:** about 2.3 CHF of LLM cost per 1,000 fields on Azure gpt-5.4-mini (script estimate; the real charge was about 70% of it).

---

## Documentation

- [wiki 01](wiki/01_project_overview.md) — the problem, who the project is for, the repository layout
- [wiki 02](wiki/02_how_it_works.md) — the nine checks, how suggestions are routed, review and write-back
- [wiki 03](wiki/03_experiment_and_validation.md) — experiment method, model comparison, training and test results
- [wiki 04](wiki/04_human_review_process.md) — the Admin's review, step by step, and what Script 2 does with each decision
- [wiki 05](wiki/05_architecture_and_reproducibility.md) — architecture, configuration, tech stack, safety and failure handling
- [wiki 06](wiki/06_lessons_learned.md) — what building it taught, for engineers new to LLM pipelines
- [ONBOARDING.md](ONBOARDING.md) for a new maintainer · [ROADMAP.md](ROADMAP.md) for what is left · [CONTRIBUTING.md](CONTRIBUTING.md) to contribute

---

## Who Does What

| Who | What they do | What they get |
|---|---|---|
| **Whoever runs the audit**: an architect, technical Admin or developer | Sets up Python and the LLM key, logs the Salesforce CLI in to a sandbox, chooses the objects, runs Script 1. A first run on the synthetic file needs no Salesforce login | A scoped inventory of weak descriptions and open questions, for cleanup or discovery |
| **Salesforce Admin and field owners** | The Admin decides Approve, Edit or Reject in the workbook; owners answer the questions about meaning and usage. Reviewing needs only the workbook and access to someone who can confirm the facts | Descriptions whose wording a person has checked |
| **Developers, integration owners, release engineers** | Verify statements about automation or mappings, then bring the approved CSV into the release process | Field definitions that say what the field is, who sets it and what reads it |
| **Learners and contributors** | Run everything on the included synthetic data, without Salesforce credentials | A complete, measured example of an LLM pipeline with human review |

---

## Contributing

Contributions are welcome.

See `CONTRIBUTING.md`.

---

## License

This project is licensed under the Apache License 2.0. See `LICENSE` and `NOTICE` for details.
