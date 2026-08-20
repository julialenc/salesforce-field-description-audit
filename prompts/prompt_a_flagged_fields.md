# Prompt A — FLAGGED Fields

## Your Task

You are receiving a batch of Salesforce fields whose descriptions have been automatically classified as **FLAGGED**. Every field in this batch has a clear, detectable description failure — it is missing, too short, self-referential, type-contradicting, picklist-incomplete, or contains placeholder language.

**For every field in the batch: write a new description.**

Do not evaluate whether a new description is needed. It is always needed for a FLAGGED field. Do not preserve or incorporate the original description — treat it as unusable.

---

## Why Each Field Was Flagged

The classifier assigned one of five rules. Use this to guide your rewrite:

**R1 — NULL or blank**
The description is missing or whitespace-only. You have no existing text to work from. Write a description entirely from the field metadata: the field name, field type, picklist values if present, formula if present, and related object if present.

**R2 — Echo or too short**
The description restates the field name or contains fewer than 30 characters of useful content. Ignore the original text and write a full description from the metadata.

**R3 — Wrong type hint**
The description describes the field as if it were a different type. For example, a Checkbox described as a text input, or a Number described as a dropdown selector. Rewrite so the description is correct for the actual field type. For a Checkbox: describe what "checked" means and what consequence it triggers. For a Number: describe what the number represents, its unit, and how it is used.

**R4 — Undefined picklist**
The field is a Picklist or MultiselectPicklist and the description never names the values. Include all picklist values in the rewrite. Format: "Values: X, Y, Z."

**R5 — Stale or placeholder**
The description contains placeholder language such as TBD, TODO, deprecated, or "no longer used." Rewrite with a proper description. If the field name and metadata suggest the field is genuinely deprecated, write a description that states this accurately and explains when it was deprecated and what replaced it, rather than leaving a blank placeholder.

---

## What to Write

A good description for this org explains:
1. What the field stores — the specific value, not a generic restatement of the field name
2. Who or what populates it — a person, a workflow, an integration, or a formula
3. What it controls or drives — a workflow trigger, a calculation input, a routing rule, an eligibility gate

Not all three are always possible from metadata alone. Write what you can confirm from the field name, type, picklist values, formula, and related object. Do not invent business logic that the metadata does not support.

---

## Input Format

You will receive a JSON array. Each element contains:
- `field_api_name` — the Salesforce API name of the field
- `field_type` — the Salesforce field type
- `description` — the current (unusable) description
- `picklist_values` — list of values if the field is a Picklist or MultiselectPicklist (may be empty)
- `formula` — the formula expression if the field is a Formula type (otherwise null)
- `related_object` — the target object if the field is a Lookup or MasterDetail (otherwise null)
- `rule_triggered` — the classifier rule that flagged this field (R1 through R5)

## Output Format

Return a JSON array in the same order as the input. For every field:
- `action` must be `"rewrite"`
- `suggested_description` must be your new description — not the original
- `reasoning` must name the rule and describe in one sentence what was wrong

```json
[
  {
    "field_api_name": "Churn_Risk_Score__c",
    "action": "rewrite",
    "suggested_description": "Numeric churn risk score calculated monthly by the predictive analytics model. Scale 0–100, where higher values indicate greater churn probability. Used to prioritise re-engagement outreach and trigger account review tasks when the score exceeds 70.",
    "reasoning": "R1: description was blank — wrote from field name and type."
  }
]
```

**Length:** aim for 60–180 characters. Do not exceed 255 characters.

**Picklist fields:** always include all values from `picklist_values` in the format "Values: X, Y, Z."

**Formula fields:** base the description on what the formula calculates. Do not describe the formula expression itself — describe the result.

**Lookup fields:** always name the related object. Format: "Reference to the [Object] record of..."
