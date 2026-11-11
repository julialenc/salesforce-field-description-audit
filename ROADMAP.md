# ROADMAP

What is left after v0.1 (November 2026), most important first. The measured state is in `wiki/03_experiment_and_validation.md`; the reasons behind each item are in `wiki/06_lessons_learned.md`.

## 1. Pilot with a real organization

The project was planned in three stages: an experiment on synthetic data, the full cycle on a Developer Edition org "as if it were real", and a pilot with a real organization. The first two are done; the third is open. It needs a Salesforce Admin or Architect working with an NGO or a small business: someone who knows how an org is run day to day, or who can follow a field into the flows, Apex and integrations that use it. Both are needed to judge whether a suggestion is right.

What to do:
- Agree with the organization to work in a **sandbox**, never in production, and on a few objects first (e.g. Account and Contact)
- Use **Azure OpenAI or another provider the organization approves**: its metadata must not go to a free tier (the scripts refuse that)
- Write the **org context file** with someone who knows the org: what its codes, tiers, scores and checkboxes mean (see `data/org_context_synthetic.md` for the shape). It was the largest lever in the experiment
- Run Script 1 with `source: org`, review the file with the organization's Admin, export the approved descriptions (`write_back: export`) and let the Admin apply them

What to measure, and record in `wiki/03_experiment_and_validation.md`:
- Share of FLAGGED suggestions the Admin approves as written; on synthetic data it was 80% on the training set and 60% on unseen fields
- How many rows need a fact only the Admin has (the Missing column), and whether the org context file answered them
- Time the Admin spent per 100 fields, and the LLM cost

This is the test that says whether the tool is useful outside synthetic data.

## 2. Help the Admin write the org context file

The org context file made the largest difference (Tab A approval 30–35% without, 70–85% with), and its coverage explained most of the gap on the test set (60%). A template, or a script that lists the Missing questions from a first run as a draft glossary for the Admin to answer, would make this step routine.

## 3. Prompt C removes sentences of good descriptions

On the dev-org run, 20 of 123 REVIEWED fields were rewritten and about 10 of those lost a sentence of the original ("Triggers priority routing to …"), more than on the training file (3 of 17). The input difference is the field label the org provides. The automatic check counts it (`dropped`). Investigate the label's effect, or keep a REVIEWED field unless the rewrite keeps every sentence.

## 4. Classifier Step 2 rules on unseen data

On the test set, R8 matched 2 of 8 labelled fields and R6 2 of 4 (training: 279/288 overall). Their keyword lists fit how the training set was written. A second, independently written dataset, or labelled fields from a real org, would show which patterns generalise.

## 5. Descriptions over 255 characters

Salesforce allows 1,000 characters; the prompts aim for 255. R7 rewrites of originals already over 255 lose a clause (Certification_Level__c). Decide whether long originals may stay long.

## 6. Free model for everyone

The prompts need about 7,500 tokens of fixed text per call, more than Groq's free tier allows per request; Cerebras works but asks for a payment method. A compact prompt variant for small free tiers would make the experiment reproducible with no account details at all. Its results would need their own measurement.

## Smaller items

- Amazon Bedrock and Google Vertex AI providers (stubs with guidance in Script 1)
- Standard fields: whether a standard field's description can be written (not needed while `include_standard_fields: false`)
- A simple runner (one command for Script 1, review, Script 2) or a web UI
