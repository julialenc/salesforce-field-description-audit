# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
seed_demo_org.py

Creates the training set's custom fields, with their deliberately messy
descriptions, in a free Salesforce Developer Edition org, so the pipeline can
be run against a real org. Standard and system fields are skipped: the org
already has them.

The script writes Salesforce DX source (one .field-meta.xml per field) into
demo_org/ and calls the Salesforce CLI. Nothing is sent to the org unless you
pass "deploy", and deploy asks for a typed confirmation first.

  python scripts/seed_demo_org.py generate
      Writes demo_org/ only. Lists the fields, nothing goes to any org.
  python scripts/seed_demo_org.py validate [--target-org sfdesc-dev]
      Check-only deploy: Salesforce compiles everything and reports errors,
      but saves nothing in the org.
  python scripts/seed_demo_org.py deploy [--target-org sfdesc-dev] [--skip Object.Field__c,...]
      Deploys the fields. Asks you to type the org alias before it starts.
  python scripts/seed_demo_org.py reset [--target-org sfdesc-dev]
      Same as deploy: puts every field's original, messy description back
      after a write-back test, so the demo can be run again.

Needs the Salesforce CLI (sf) and a logged-in org:
  sf org login web --alias sfdesc-dev
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT        = Path(__file__).resolve().parent.parent
DATASET     = ROOT / "data" / "sf_metadata_raw_training.json"
OUT_DIR     = ROOT / "demo_org"
API_VERSION = "62.0"
DEFAULT_ORG = "sfdesc-dev"

TEXT_LENGTH      = 255
NUMBER_PRECISION = 18
NUMBER_SCALE     = 2
# Salesforce field types as written in the dataset -> metadata <type>
TYPE_MAP = {
    "Text": "Text", "Checkbox": "Checkbox", "Number": "Number", "Currency": "Currency",
    "Percent": "Percent", "Date": "Date", "DateTime": "DateTime", "Email": "Email",
    "Phone": "Phone", "URL": "Url", "Picklist": "Picklist",
    "MultiselectPicklist": "MultiselectPicklist", "Lookup": "Lookup",
}


def load_custom_fields(path: Path = DATASET) -> list[dict]:
    data   = json.loads(path.read_text(encoding="utf-8"))
    fields = data.get("fields", data) if isinstance(data, dict) else data
    return [f for f in fields if f.get("field_api_name", "").endswith("__c")]


def label_for(api_name: str) -> str:
    """Field label from the API name: Last_Order_Date__c -> Last Order Date (max 40 characters)."""
    return re.sub(r"__c$", "", api_name).replace("_", " ").strip()[:40]


def field_xml(f: dict) -> str:
    """CustomField metadata for one dataset field."""
    name, ftype = f["field_api_name"], f["field_type"]
    if ftype not in TYPE_MAP:
        raise ValueError(f"{f['object']}.{name}: field type {ftype} is not supported")
    parts = [f"    <fullName>{escape(name)}</fullName>"]
    if f.get("description"):
        parts.append(f"    <description>{escape(f['description'])}</description>")
    parts.append(f"    <label>{escape(label_for(name))}</label>")

    if f.get("formula"):
        # Formula fields: the result type, no length or default
        result = {"Text": "Text", "Number": "Number", "Currency": "Currency",
                  "Date": "Date", "Checkbox": "Checkbox"}.get(ftype, "Text")
        parts.append(f"    <formula>{escape(f['formula'])}</formula>")
        parts.append("    <formulaTreatBlanksAs>BlankAsZero</formulaTreatBlanksAs>")
        if result in ("Number", "Currency"):
            parts += [f"    <precision>{NUMBER_PRECISION}</precision>", f"    <scale>{NUMBER_SCALE}</scale>"]
        parts.append(f"    <type>{result}</type>")
        return _wrap(parts)

    mtype = TYPE_MAP[ftype]
    if mtype == "Text":
        parts.append(f"    <length>{TEXT_LENGTH}</length>")
    elif mtype == "Checkbox":
        parts.append("    <defaultValue>false</defaultValue>")
    elif mtype in ("Number", "Currency", "Percent"):
        parts += [f"    <precision>{NUMBER_PRECISION}</precision>", f"    <scale>{NUMBER_SCALE}</scale>"]
    elif mtype in ("Picklist", "MultiselectPicklist"):
        values = f.get("picklist_values") or ["Placeholder"]
        if mtype == "MultiselectPicklist":
            parts.append("    <visibleLines>4</visibleLines>")
        parts.append("    <valueSet>\n        <restricted>true</restricted>\n        <valueSetDefinition>\n"
                     "            <sorted>false</sorted>")
        for v in values:
            parts.append(f"            <value>\n                <fullName>{escape(v)}</fullName>\n"
                         f"                <default>false</default>\n                <label>{escape(v)}</label>\n"
                         f"            </value>")
        parts.append("        </valueSetDefinition>\n    </valueSet>")
    elif mtype == "Lookup":
        rel = re.sub(r"__c$", "", name)
        parts += ["    <deleteConstraint>SetNull</deleteConstraint>",
                  f"    <referenceTo>{escape(f['related_object'])}</referenceTo>",
                  f"    <relationshipLabel>{escape(label_for(f['object'] + '_' + rel))}</relationshipLabel>",
                  f"    <relationshipName>{escape(f['object'] + '_' + rel)}</relationshipName>"]
    parts.append(f"    <type>{mtype}</type>")
    return _wrap(parts)


def _wrap(parts: list[str]) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">\n'
            + "\n".join(parts) + "\n</CustomField>\n")


def generate(skip: set[str]) -> list[dict]:
    """Write demo_org/ as a Salesforce DX project. Returns the fields written."""
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    objects_dir = OUT_DIR / "force-app" / "main" / "default" / "objects"
    (OUT_DIR / "sfdx-project.json").parent.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sfdx-project.json").write_text(json.dumps({
        "packageDirectories": [{"path": "force-app", "default": True}],
        "sourceApiVersion": API_VERSION,
    }, indent=2), encoding="utf-8")
    written = []
    for f in load_custom_fields():
        key = f"{f['object']}.{f['field_api_name']}"
        if key in skip:
            continue
        path = objects_dir / f["object"] / "fields" / f"{f['field_api_name']}.field-meta.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(field_xml(f), encoding="utf-8")
        written.append(f)
    return written


def run_cli(args: list[str]) -> dict:
    sf = shutil.which("sf") or shutil.which("sf.cmd")
    if not sf:
        print("Salesforce CLI not found. Install it (npm install -g @salesforce/cli) and log in:\n"
              f"  sf org login web --alias {DEFAULT_ORG}")
        sys.exit(2)
    proc = subprocess.run([sf, *args, "--json"], cwd=OUT_DIR, capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout[-2000:], proc.stderr[-2000:])
        sys.exit(2)


def report(result: dict) -> int:
    """Print deploy or validate results: counts and every failed component."""
    r = result.get("result") or {}
    if not r:                              # the CLI failed before a deploy result existed
        print(f"Failed: {result.get('message', result)}")
        return 1
    details  = r.get("details") or {}
    failures = details.get("componentFailures") or []
    if isinstance(failures, dict):
        failures = [failures]
    print(f"Status: {r.get('status', result.get('message', 'unknown'))}  "
          f"components {r.get('numberComponentsDeployed', 0)}/{r.get('numberComponentsTotal', 0)} ok, "
          f"{r.get('numberComponentErrors', len(failures))} errors")
    for fail in failures:
        print(f"  FAIL {fail.get('fullName')}: {fail.get('problem')}")
    return 0 if r.get("success") else 1


def main() -> int:
    args    = sys.argv[1:]
    command = args[0] if args else "generate"
    org     = args[args.index("--target-org") + 1] if "--target-org" in args else DEFAULT_ORG
    skip    = set(args[args.index("--skip") + 1].split(",")) if "--skip" in args else set()

    fields = generate(skip)
    by_object: dict[str, int] = {}
    for f in fields:
        by_object[f["object"]] = by_object.get(f["object"], 0) + 1
    print(f"Wrote {len(fields)} custom fields to {OUT_DIR.relative_to(ROOT)}/: "
          + ", ".join(f"{o} {n}" for o, n in by_object.items())
          + (f" (skipped {len(skip)})" if skip else ""))
    if command == "generate":
        return 0

    source = ["--source-dir", "force-app", "--target-org", org, "--wait", "30"]
    if command == "validate":
        print(f"Check-only deploy to {org}: nothing is saved in the org.")
        return report(run_cli(["project", "deploy", "validate", *source]))
    if command in ("deploy", "reset"):
        print(f"This creates or resets {len(fields)} custom fields in the org '{org}' (original descriptions).")
        if input(f"Type the org alias ({org}) to continue: ").strip() != org:
            print("Cancelled. Nothing was deployed.")
            return 1
        return report(run_cli(["project", "deploy", "start", *source]))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
