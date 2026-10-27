# Prompt A — FLAGGED Fields

## Your Task

You are receiving a batch of Salesforce fields whose descriptions have been automatically classified as **FLAGGED**. Every field in this batch has a clear, detectable description failure — it is missing, too short, self-referential, type-contradicting, picklist-incomplete, or contains placeholder language.

**For every field in the batch: write a new description.**

Do not evaluate whether a new description is needed. It is always needed for a FLAGGED field. The original fails a check, but it is still input: keep every fact it states (values, tiers, event types, system names, caveats) and drop only what is wrong — the wrong type wording, the placeholder words, the instruction to the user.

---

## Why Each Field Was Flagged

The classifier assigned one of five rules. Use this to guide your rewrite:

**R1 — NULL or blank**
The description is missing or whitespace-only. You have no existing text to work from. Write a description entirely from the field metadata: the field name, field type, picklist values if present, formula if present, and related object if present.

**R2 — Echo or too short**
The description restates the field name or contains fewer than 30 characters of useful content. Write the description from the metadata; keep the little the original says, if it is true.

**R3 — Wrong type hint**
The description describes the field as if it were a different type. For example, a Checkbox described as a text input, or a Number described as a dropdown selector. Rewrite so the description is correct for the actual field type, and keep the original's content in a form the type can hold. For a Checkbox: say what "checked" means, if the input tells you; otherwise ask. For a Number: say what the number represents; if the original lists tiers or bands ("Standard, Silver, Gold"), keep their names and ask how they map to the number.

**R4 — Undefined picklist**
The field is a Picklist or MultiselectPicklist and the description never names the values. Include all picklist values in the rewrite. Format: "Values: X, Y, Z." Do not guess values that do not explain themselves (letters, codes, Alpha–Delta): explain them from the org context if it defines them, otherwise ask what they mean.

**R5 — Stale or placeholder**
The description contains placeholder language such as TBD, TODO, deprecated, or "no longer used." Rewrite with a proper description. The original's status and caveat are facts: if it says the field is deprecated, not used for routing, or waiting for legal approval, the rewrite says exactly that, no stronger and no weaker. Do not add when it was deprecated, what replaced it or whether it is still populated; ask in `missing` if the description needs it.

---

## What to Write

A complete description explains:
1. What the field stores — the specific value, not a generic restatement of the field name
2. Who or what populates it — a person, a workflow, an integration, or a formula
3. What it controls or drives — a workflow trigger, a calculation input, a routing rule, an eligibility gate

Write only the parts the input confirms. A blank or one-word original usually confirms only the first, and often only in part: then write a short, accurate description and ask for the rest in `missing` (see "What to ask in `missing`" in the system prompt). Do not write a likely guess into the text.

---

## Input Format

You will receive a JSON array. Each element contains:
- `field_api_name` — the Salesforce API name of the field
- `field_type` — the Salesforce field type
- `description` — the current description (failed a check, but its facts are input)
- `picklist_values` — list of values if the field is a Picklist or MultiselectPicklist (may be empty)
- `formula` — the formula expression if the field is a Formula type (otherwise null)
- `related_object` — the target object if the field is a Lookup or MasterDetail (otherwise null)
- `rule_triggered` — the classifier rule that flagged this field (R1 through R5)
- `neighbour_fields` — other fields on the same object with a shared name word (may be absent)
- `label`, `help_text`, `length`, `decimal_places` — further metadata, only when the org provides it

## Output Format

Return a JSON array in the same order as the input. For every field:
- `action` must be `"rewrite"`
- `suggested_description` must be your new description — not the original
- `reasoning` must name the rule and describe in one sentence what was wrong
- `assumptions` lists every claim in your description that the input does not support (see the system prompt); `[]` if there are none
- `missing` lists, as questions, the facts the description needs but the input does not give; `[]` if there are none

```json
[
  {
    "field_api_name": "Renewal_Risk_Score__c",
    "action": "rewrite",
    "suggested_description": "Score estimating the risk that this account will not renew its service contract.",
    "reasoning": "R1: description was blank — wrote from the field name and type; range, direction and source are unknown and asked for.",
    "assumptions": [],
    "missing": ["What is the score's range, and does a higher value mean higher risk?", "Which process or model sets the score?"]
  },
  {
    "field_api_name": "Freight_Weight_Kg__c",
    "action": "rewrite",
    "suggested_description": "Weight of this shipment in kilograms, stored as a single number. The weight band (Light, Medium or Heavy) depends on this value.",
    "reasoning": "R3: a Number field was described as a dropdown; kept the band names from the original as a dependency and asked for the limits.",
    "assumptions": [],
    "missing": ["Which weights separate Light, Medium and Heavy?", "Is this gross or net weight?"]
  },
  {
    "field_api_name": "Legacy_Region_Code__c",
    "action": "rewrite",
    "suggested_description": "Deprecated. Sales region code from the 2019 territory model. No longer read by account assignment rules.",
    "reasoning": "R5: kept the original's status and caveat exactly; removed the placeholder wording.",
    "assumptions": [],
    "missing": ["Is the field still populated on new accounts?"]
  }
]
```

**Length:** aim for 60–180 characters. Do not exceed 255 characters.

**Picklist fields:** always include all values from `picklist_values` in the format "Values: X, Y, Z."

**Formula fields:** base the description on what the formula calculates. Do not describe the formula expression itself — describe the result.

**Lookup fields:** always name the related object. Format: "Reference to the [Object] record of..."

---

## Check Before You Answer

Read each `suggested_description` once more and fix it if any of these fail:
1. **Length:** at least 30 and at most 255 characters, counted including spaces. If it is longer, cut process detail, not facts. If it is shorter, add what the field type and name confirm (e.g. "Stored as a single date.").
1b. **Standard acronyms:** an acronym from the field name or the original that has a standard expansion (NPS, EBR, CSAT) is expanded, and the expansion is listed in `assumptions` unless the input gives it.
2. **Acronyms:** every acronym is expanded in brackets on first use, e.g. "NPS (Net Promoter Score)". This includes acronyms taken from the field name (NPS, RFM, EBR). Picklist values are written exactly as given and need no expansion. If you do not know what an acronym stands for, write the idea in plain words instead. Do not add acronyms that are not in the input.
3. **Forbidden terms:** none of "relevant", "applicable", "various", "related to", "for tracking", "for reporting", "for reference", "internal use". Name the specific report, team, rule or system instead, or leave the clause out.
4. **Picklist values:** every value from `picklist_values` appears, spelled exactly as given.
5. **Nothing guessed:** every person, team, process, system, scale, direction or consequence you named is in the input. If not, take it out of the text and ask for it in `missing`; keep it only if it is a confident reading listed in `assumptions` (see the system prompt). The description contains no question and no remark about what is unknown; those belong in `missing`. Sentences such as "Used by …", "Read by …", "Populated by …", "Set by …", "Drives …", "Enables …" and words such as "manual" or "automatic" must come from the input; delete them otherwise.
6. **Nothing lost:** every value, tier, event type, system name and caveat of the original is still there, with the same strength.
7. **Missing:** at most three questions, the type's question first (range and unit, what checked means, what codes mean, which event).
