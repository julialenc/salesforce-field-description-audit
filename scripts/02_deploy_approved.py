# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
02_deploy_approved.py

Script 2 of the Salesforce Field Description Automation pipeline.

Workflow:
  1. Read config.yml
  2. Find the most recent review_queue_{timestamp}.xlsx in data/
     (or use the file given as argument)
  3. Read Admin decisions from Tab A and Tab B
  4. Validate the review file — stop if any row is incomplete or invalid
  5. Apply approved changes, as set by write_back in config.yml:
       - off:    dry run — log decisions, write nothing
       - export: write approved descriptions to approved_descriptions_{timestamp}.csv
                 for the Admin to apply by hand (default)
       - deploy: write them to salesforce.target_org through the Salesforce CLI:
                 retrieve each field's metadata, change only its description,
                 deploy. Asks for the org alias to be typed first. A field that
                 fails (e.g. no longer exists) is logged and the rest go through
     A row whose new description equals the current one is logged as
     UNCHANGED and not written (e.g. a retired field the LLM kept)
  6. Write write_log_{timestamp}.xlsx

Usage:
  python scripts/02_deploy_approved.py [data/review_queue_<timestamp>.xlsx]

See wiki/02_how_it_works.md for full pipeline documentation.
"""

import csv
import json
import logging
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import yaml
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sf_cli  # noqa: E402  (Salesforce CLI helpers, next to this script)

# ── logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────

ROOT        = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_DIR    = ROOT / "data"

# ── constants ─────────────────────────────────────────────────────────────────

VALID_DECISIONS   = {"Approve", "Edit", "Reject"}
MAX_DESC_LENGTH   = 1000   # Salesforce limit for a field description (checked in a Developer Edition org)

# Column names expected in Tab A and Tab B of the review file
COL_OBJECT        = "Object"
COL_API_NAME      = "Field_API_Name"
COL_CURRENT_DESC  = "Current_Description"
COL_LLM_SUGGEST   = "LLM_Suggestion"
COL_DECISION      = "Decision"
COL_ADMIN_VERSION = "Admin_Version"


# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIG
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        log.error("config.yml not found. Copy config.example.yml to config.yml and fill in your values.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    cfg["write_back"] = write_back_mode(cfg)
    log.info(f"Config loaded — write_back: {cfg['write_back']}")
    return cfg


def write_back_mode(cfg: dict) -> str:
    """off | export | deploy. YAML reads a bare off as false; old configs used mode: experiment | production."""
    value = cfg.get("write_back")
    if value is False:
        return "off"
    if value is None:
        return {"experiment": "off", "production": "deploy"}.get(cfg.get("mode"), "export")
    if value not in ("off", "export", "deploy"):
        log.error(f"config.yml: write_back must be off, export or deploy, not '{value}'")
        sys.exit(1)
    return value


# ─────────────────────────────────────────────────────────────────────────────
# 2. FIND REVIEW FILE
# ─────────────────────────────────────────────────────────────────────────────

def find_review_file() -> Path:
    """The review file given as argument, or the most recent review_queue_{timestamp}.xlsx in data/."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        chosen = Path(args[0])
        if not chosen.is_absolute():
            chosen = ROOT / chosen
        if not chosen.exists():
            log.error(f"Review file not found: {chosen}")
            sys.exit(1)
        log.info(f"Review file: {chosen.name}")
        return chosen
    candidates = sorted(
        DATA_DIR.glob("review_queue_*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        log.error(
            "No review_queue_{timestamp}.xlsx found in data/. "
            "Run Script 1 first to generate the review file."
        )
        sys.exit(1)
    chosen = candidates[0]
    log.info(f"Review file: {chosen.name}")
    if len(candidates) > 1:
        log.warning(
            f"{len(candidates)} review files found — using the most recent. "
            f"Older files: {[p.name for p in candidates[1:]]}"
        )
    return chosen


# ─────────────────────────────────────────────────────────────────────────────
# 3. READ DECISIONS
# ─────────────────────────────────────────────────────────────────────────────

def read_decisions(review_path: Path) -> list[dict]:
    """
    Read all actionable rows from Tab A and Tab B.
    Returns list of dicts with the Admin's decision for each field.
    """
    wb = openpyxl.load_workbook(review_path, data_only=True)

    action_sheets = []
    for sheet_name in wb.sheetnames:
        if "Tab A" in sheet_name or "Tab B" in sheet_name:
            action_sheets.append(wb[sheet_name])

    if not action_sheets:
        log.error("Could not find 'Tab A' or 'Tab B' in the review file. Check the sheet names.")
        sys.exit(1)

    rows = []
    for ws in action_sheets:
        sheet_rows = _read_sheet(ws)
        log.info(f"  {ws.title}: {len(sheet_rows)} rows read")
        rows.extend(sheet_rows)

    log.info(f"Total actionable rows: {len(rows)}")
    return rows


def _read_sheet(ws) -> list[dict]:
    """Parse a worksheet into list of row dicts using header row."""
    headers = {}
    for cell in ws[1]:
        if cell.value:
            headers[str(cell.value).strip()] = cell.column - 1  # 0-indexed

    required_cols = [COL_OBJECT, COL_API_NAME, COL_LLM_SUGGEST, COL_DECISION]
    for col in required_cols:
        if col not in headers:
            log.error(f"Required column '{col}' not found in sheet '{ws.title}'. Headers found: {list(headers.keys())}")
            sys.exit(1)

    rows = []
    for excel_row, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue
        def get(col_name: str) -> str:
            idx = headers.get(col_name)
            if idx is None:
                return ""
            val = row[idx] if idx < len(row) else None
            return str(val).strip() if val is not None else ""

        rows.append({
            "sheet":          ws.title,
            "excel_row":      excel_row,
            "object":         get(COL_OBJECT),
            "field_api_name": get(COL_API_NAME),
            "current_desc":   get(COL_CURRENT_DESC),
            "llm_suggestion": get(COL_LLM_SUGGEST),
            "decision":       get(COL_DECISION),
            "admin_version":  get(COL_ADMIN_VERSION),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 4. VALIDATE
# ─────────────────────────────────────────────────────────────────────────────

def validate_decisions(rows: list[dict]) -> list[str]:
    """
    Validate all rows before any write begins.
    Returns list of error messages. Empty list = valid.
    """
    errors = []
    for row in rows:
        # Point at the sheet and Excel row, e.g. "Tab B — UNCERTAIN row 12"
        i        = f"{row.get('sheet', '')} row {row.get('excel_row', '?')}"
        name     = f"{row.get('object', '')}.{row.get('field_api_name', '')}"
        decision = row.get("decision", "")

        # Every row must have a decision
        if not decision:
            errors.append(f"{i} ({name}): Decision is missing.")
            continue

        # Decision must be one of the valid values
        if decision not in VALID_DECISIONS:
            errors.append(
                f"{i} ({name}): Invalid decision '{decision}'. "
                f"Must be one of: {', '.join(sorted(VALID_DECISIONS))}"
            )
            continue

        # Edit rows must have an Admin_Version
        if decision == "Edit":
            admin_ver = row.get("admin_version", "").strip()
            if not admin_ver:
                errors.append(f"{i} ({name}): Decision is 'Edit' but Admin_Version is empty.")
            elif len(admin_ver) > MAX_DESC_LENGTH:
                errors.append(
                    f"{i} ({name}): Admin_Version is {len(admin_ver)} characters "
                    f"(maximum is {MAX_DESC_LENGTH})."
                )

        # Approve rows — check that the LLM suggestion fits the limit
        if decision == "Approve":
            suggestion = row.get("llm_suggestion", "").strip()
            if len(suggestion) > MAX_DESC_LENGTH:
                errors.append(
                    f"{i} ({name}): LLM_Suggestion is {len(suggestion)} characters "
                    f"(maximum is {MAX_DESC_LENGTH}). Change decision to Edit and provide a shorter version."
                )

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# 5. DEPLOY
# ─────────────────────────────────────────────────────────────────────────────

def deploy(rows: list[dict], cfg: dict) -> list[dict]:
    """
    Apply the decisions as set by write_back (off | export | deploy).
    Returns list of write log records.
    """
    mode = cfg.get("write_back", "export")
    log_records, to_write = [], []

    for row in rows:
        if row["decision"] == "Reject":
            log_records.append(_log_record(row, "SKIPPED", "Decision: Reject — no change written."))
            continue
        new_desc = row["admin_version"].strip() if row["decision"] == "Edit" else row["llm_suggestion"].strip()
        if new_desc == row.get("current_desc", "").strip():
            log_records.append(_log_record(row, "UNCHANGED", "Same as the current description — nothing to write.", new_desc))
            continue
        to_write.append((row, new_desc))

    if mode == "off":
        log.info("write_back: off — dry run, nothing is written")
        log_records += [_log_record(r, "DRY_RUN", f"Would write: {d[:80]}...", d) for r, d in to_write]
    elif mode == "export":
        path = export_csv(to_write)
        log_records += [_log_record(r, "EXPORTED", f"In {path.name}", d) for r, d in to_write]
    else:
        log_records += deploy_to_org(to_write, cfg)

    counts = {s: sum(1 for r in log_records if r["write_status"] == s)
              for s in ("SUCCESS", "EXPORTED", "DRY_RUN", "UNCHANGED", "SKIPPED", "FAILED")}
    log.info("Done — " + ", ".join(f"{n} {s.lower()}" for s, n in counts.items() if n))
    return log_records


def export_csv(to_write: list[tuple[dict, str]]) -> Path:
    """Approved descriptions as a CSV the Admin can apply by hand (Setup or a deployment tool)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"approved_descriptions_{timestamp}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:      # utf-8-sig: Excel opens it correctly
        w = csv.writer(f)
        w.writerow(["Object", "Field_API_Name", "Decision", "Old_Description", "New_Description"])
        for row, new_desc in to_write:
            w.writerow([row["object"], row["field_api_name"], row["decision"], row.get("current_desc", ""), new_desc])
    log.info(f"Exported {len(to_write)} approved descriptions to {path.name}")
    return path


def deploy_to_org(to_write: list[tuple[dict, str]], cfg: dict) -> list[dict]:
    """
    Write descriptions to the org through the Salesforce CLI: retrieve the
    fields' metadata, change only <description>, deploy. Fields that fail are
    logged as FAILED; the others are saved (the deploy is not all-or-nothing).
    """
    org = (cfg.get("salesforce") or {}).get("target_org")
    if not org:
        log.error("config.yml: write_back: deploy needs salesforce.target_org (the alias used in sf org login web)")
        sys.exit(1)
    if not to_write:
        return []
    log.info(f"About to write {len(to_write)} field descriptions to the org '{org}'.")
    if input(f"Type the org alias ({org}) to continue: ").strip() != org:
        log.error("Cancelled. Nothing was written.")
        sys.exit(1)

    records = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:    # Windows: the CLI may still hold the folder
        names = [f"CustomField:{r['object']}.{r['field_api_name']}" for r, _ in to_write]
        sf_cli.run(["project", "retrieve", "start", "--target-org", org, "--target-metadata-dir", tmp,
                    "--unzip", "--wait", "30", "--metadata", *names], check=False)
        package = next(Path(tmp).rglob("package.xml"), None)
        found = _set_descriptions(package.parent, to_write) if package else set()

        for row, new_desc in to_write:
            if (row["object"], row["field_api_name"]) not in found:
                records.append(_log_record(row, "FAILED", "Field not found in the org.", new_desc))
        if not found:
            return records
        _write_package(package, found)            # the retrieve's package.xml also names the missing fields

        result  = sf_cli.run(["project", "deploy", "start", "--target-org", org, "--metadata-dir",
                              str(package.parent), "--ignore-errors", "--wait", "30"], check=False)
        details = (result.get("result") or {}).get("details") or {}
        fails   = details.get("componentFailures") or []
        fails   = [fails] if isinstance(fails, dict) else fails
        failed  = {f.get("fullName"): f.get("problem", "") for f in fails}
        if not result.get("result"):
            failed = {f"{o}.{n}": result.get("message", "deploy failed") for o, n in found}
        for row, new_desc in to_write:
            key = (row["object"], row["field_api_name"])
            if key not in found:
                continue
            problem = failed.get(f"{key[0]}.{key[1]}")
            records.append(_log_record(row, "FAILED" if problem is not None else "SUCCESS",
                                       problem or "Written to the org.", new_desc))
    return records


def _write_package(package: Path, fields: set[tuple[str, str]]) -> None:
    """package.xml naming exactly the fields to deploy."""
    members = "\n".join(f"        <members>{o}.{n}</members>" for o, n in sorted(fields))
    package.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<Package xmlns="http://soap.sforce.com/2006/04/metadata">\n'
                       f'    <types>\n{members}\n        <name>CustomField</name>\n    </types>\n'
                       f'    <version>{sf_cli.API_VERSION}</version>\n</Package>\n', encoding="utf-8")


def _set_descriptions(mdapi_dir: Path, to_write: list[tuple[dict, str]]) -> set[tuple[str, str]]:
    """Change only <description> in the retrieved metadata. Returns the (object, field) pairs found."""
    ns = sf_cli.NS["m"]
    ET.register_namespace("", ns)
    wanted = {(r["object"], r["field_api_name"]): d for r, d in to_write}
    found = set()
    for path in mdapi_dir.rglob("*.object"):
        obj  = path.stem
        tree = ET.parse(path)
        for el in tree.getroot().findall(f"{{{ns}}}fields"):
            name = el.findtext(f"{{{ns}}}fullName")
            if (obj, name) not in wanted:
                continue
            desc = el.find(f"{{{ns}}}description")
            if desc is None:                      # description goes right after fullName
                desc = ET.Element(f"{{{ns}}}description")
                el.insert(1, desc)
            desc.text = wanted[(obj, name)]
            found.add((obj, name))
        tree.write(path, encoding="UTF-8", xml_declaration=True)
    return found


def _log_record(row: dict, status: str, message: str, new_desc: str = "") -> dict:
    return {
        "object":          row.get("object", ""),
        "field_api_name":  row.get("field_api_name", ""),
        "decision":        row.get("decision", ""),
        "old_description": row.get("current_desc", ""),
        "new_description": new_desc,
        "write_status":    status,
        "message":         message,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. WRITE LOG
# ─────────────────────────────────────────────────────────────────────────────

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=10)
CELL_FONT   = Font(name="Arial", size=9)
CENTER_AL   = Alignment(horizontal="center", vertical="top", wrap_text=True)
LEFT_AL     = Alignment(horizontal="left",   vertical="top", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)

STATUS_FILL = {
    "SUCCESS": PatternFill("solid", fgColor="D7F0D7"),
    "DRY_RUN": PatternFill("solid", fgColor="D7EEFF"),
    "EXPORTED": PatternFill("solid", fgColor="D7EEFF"),
    "UNCHANGED": PatternFill("solid", fgColor="E8E8E8"),
    "SKIPPED": PatternFill("solid", fgColor="E8E8E8"),
    "FAILED":  PatternFill("solid", fgColor="FFD7D7"),
}


def write_log(log_records: list[dict]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path  = DATA_DIR / f"write_log_{timestamp}.xlsx"
    wb        = openpyxl.Workbook()
    ws        = wb.active
    ws.title  = "Write Log"

    headers = [
        "Object", "Field_API_Name", "Decision",
        "Old_Description", "New_Description",
        "Write_Status", "Message", "Timestamp",
    ]
    col_widths = {
        "Object": 14, "Field_API_Name": 32, "Decision": 12,
        "Old_Description": 55, "New_Description": 55,
        "Write_Status": 14, "Message": 45, "Timestamp": 22,
    }

    # Header row
    ws.row_dimensions[1].height = 28
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font, c.fill, c.alignment, c.border = HEADER_FONT, HEADER_FILL, CENTER_AL, THIN_BORDER
        ws.column_dimensions[get_column_letter(ci)].width = col_widths.get(h, 18)

    # Data rows
    field_map = {
        "Object":          "object",
        "Field_API_Name":  "field_api_name",
        "Decision":        "decision",
        "Old_Description": "old_description",
        "New_Description": "new_description",
        "Write_Status":    "write_status",
        "Message":         "message",
        "Timestamp":       "timestamp",
    }
    for ri, record in enumerate(log_records, 2):
        status = record.get("write_status", "")
        fill   = STATUS_FILL.get(status, PatternFill("solid", fgColor="FFFFFF"))
        for ci, h in enumerate(headers, 1):
            val = record.get(field_map[h], "")
            c   = ws.cell(row=ri, column=ci, value=val)
            c.font, c.fill, c.border = CELL_FONT, fill, THIN_BORDER
            c.alignment = CENTER_AL if h in ("Object", "Decision", "Write_Status") else LEFT_AL

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "A2"

    # Summary tab
    ws2 = wb.create_sheet("Summary")
    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 12

    from collections import Counter
    status_counts = Counter(r["write_status"] for r in log_records)
    summary_rows  = [
        ("Generated at (UTC)", timestamp),
        ("Total rows processed", len(log_records)),
        ("Written (SUCCESS)",   status_counts.get("SUCCESS", 0)),
        ("Dry-run (DRY_RUN)",   status_counts.get("DRY_RUN", 0)),
        ("Exported to CSV (EXPORTED)", status_counts.get("EXPORTED", 0)),
        ("Unchanged (UNCHANGED)", status_counts.get("UNCHANGED", 0)),
        ("Rejected (SKIPPED)",  status_counts.get("SKIPPED", 0)),
        ("Failed (FAILED)",     status_counts.get("FAILED",  0)),
    ]
    for ri, (label, val) in enumerate(summary_rows, 1):
        ws2.cell(row=ri, column=1, value=label).font = Font(name="Arial", size=9, bold=True)
        ws2.cell(row=ri, column=2, value=val).font   = Font(name="Arial", size=9)

    wb.save(out_path)
    log.info(f"Write log saved: {out_path.name}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("Script 2 — Deploy Approved")
    log.info("=" * 60)

    # 1. Config
    cfg = load_config()

    # 2. Find review file
    review_path = find_review_file()

    # 3. Read decisions
    rows = read_decisions(review_path)
    if not rows:
        log.warning("No actionable rows found in the review file. Nothing to deploy.")
        sys.exit(0)

    # 4. Validate — stop entirely if anything is wrong
    errors = validate_decisions(rows)
    if errors:
        log.error(f"Validation failed — {len(errors)} error(s) found. Nothing has been written.")
        for err in errors:
            log.error(f"  {err}")
        log.error("Fix the review file and run Script 2 again.")
        sys.exit(1)

    log.info(f"Validation passed — {len(rows)} rows ready for deployment")

    # Decision summary
    from collections import Counter
    decisions = Counter(r["decision"] for r in rows)
    log.info(
        f"Decisions: Approve={decisions.get('Approve', 0)}, "
        f"Edit={decisions.get('Edit', 0)}, "
        f"Reject={decisions.get('Reject', 0)}"
    )

    # 5. Deploy
    log_records = deploy(rows, cfg)

    # 6. Write log
    write_log(log_records)

    log.info("=" * 60)
    log.info("Script 2 complete.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
