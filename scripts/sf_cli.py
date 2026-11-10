# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
sf_cli.py

Small helpers around the Salesforce CLI (sf), shared by the scripts. The CLI
holds the org login (sf org login web --alias <alias>), so no username,
password or token is ever stored in config.yml, and no Salesforce Python
package is needed.

read_fields(org, objects) retrieves the CustomObject metadata of each object
(a read-only Metadata API retrieve) and returns its fields in the pipeline's
field format. Metadata retrieve is used instead of a describe call because
describe hides fields the running user cannot see (field-level security),
while the metadata always lists every field with its description.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"m": "http://soap.sforce.com/2006/04/metadata"}

# Metadata <type> -> the field type names the pipeline and datasets use
TYPE_NAMES = {"Url": "URL"}


def find_sf() -> str:
    sf = shutil.which("sf") or shutil.which("sf.cmd")
    if not sf:
        print("Salesforce CLI not found. Install it (https://developer.salesforce.com/tools/salesforcecli) "
              "and log in:\n  sf org login web --alias <alias>")
        sys.exit(2)
    return sf


def run(args: list[str], cwd: Path | None = None) -> dict:
    """Run an sf command with --json and return the parsed result. Exits with the CLI's message on failure."""
    proc = subprocess.run([find_sf(), *args, "--json"], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout[-2000:], proc.stderr[-2000:])
        sys.exit(2)
    if data.get("status", 1) != 0:
        print(f"Salesforce CLI error: {data.get('message', data)}")
        sys.exit(2)
    return data


def read_fields(org: str, objects: list[str], include_standard: bool = False) -> list[dict]:
    """Every field of the given objects, from a read-only metadata retrieve. Custom fields only unless include_standard."""
    with tempfile.TemporaryDirectory() as tmp:
        run(["project", "retrieve", "start", "--target-org", org, "--target-metadata-dir", tmp,
             "--unzip", "--wait", "30", "--metadata", *[f"CustomObject:{o}" for o in objects]], cwd=Path(tmp))
        fields = []
        for obj in objects:
            files = list(Path(tmp).rglob(f"objects/{obj}.object"))
            if not files:
                print(f"Warning: no metadata retrieved for {obj}")
                continue
            root = ET.parse(files[0]).getroot()
            for el in root.findall("m:fields", NS):
                f = _field_from_xml(obj, el)
                if include_standard or f["field_api_name"].endswith("__c"):
                    fields.append(f)
    return fields


def _field_from_xml(obj: str, el: ET.Element) -> dict:
    text = lambda tag: el.findtext(f"m:{tag}", namespaces=NS)
    ftype = text("type") or ""
    return {
        "object":          obj,
        "field_api_name":  text("fullName"),
        "field_type":      TYPE_NAMES.get(ftype, ftype),
        "description":     text("description"),
        "picklist_values": [v.findtext("m:fullName", namespaces=NS)
                            for v in el.findall("m:valueSet/m:valueSetDefinition/m:value", NS)],
        "formula":         text("formula"),
        "related_object":  text("referenceTo"),
        "label":           text("label"),
        "help_text":       text("inlineHelpText"),
        "length":          int(text("length")) if text("length") else None,
        "decimal_places":  int(text("scale")) if text("scale") else None,
    }
