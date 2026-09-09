"""Read a reviewer's data-request workbook, and write one back.

DNV issues a spreadsheet - an Issue ID, a description, a column for our notes,
a column for theirs, and a validated Status - and expects it back filled in.
Rebuilding that checklist by hand in this app would be the same work twice, so
the workbook is imported once to become a template, and afterwards it is an
output: their own file, their own formatting, our columns filled from the live
report.

Two rules make the round trip safe. The original is never written to - a filled
copy is generated each time - and the Status column is only ever given a value
the workbook's own validation accepts.
"""
import os
import openpyxl
from openpyxl.utils import column_index_from_string as _col

# A section header rather than a requirement. DNV numbers sections 1000, 2000,
# ... 10000 and the requirements under them 1001, 1002, so a whole multiple of a
# thousand is the divider. It holds for the awkward-looking 4100 and 4200, which
# are requirements.
SECTION_STEP = 1000


def _num(v):
    """The Issue ID as an integer, or None if this row does not carry one."""
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except ValueError:
        return None


def _text(v):
    return "" if v is None else str(v).strip()


def sheet_names(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    names = wb.sheetnames
    wb.close()
    return names


def parse(path, sheet="", header_row=3, id_col="A", desc_col="B", evidence_col="C"):
    """Pull the sections and requirements out of a data-request workbook.

    Returns the template shape this app stores: a name, and sections each
    holding their items in sheet order. Rows above the header, and the preamble
    rows that carry text but no Issue ID, are skipped - they are instructions to
    the reader, not requirements.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
    idx = {k: _col(v) for k, v in
           (("id", id_col), ("desc", desc_col), ("evid", evidence_col))}

    # The title usually sits in the merged cell above the header row.
    title = ""
    for r in range(1, max(header_row, 1)):
        t = _text(ws.cell(r, idx["id"]).value) or _text(ws.cell(r, idx["desc"]).value)
        if len(t) > len(title):
            title = t
    # Titles are often typed across two lines inside one merged cell.
    name = " ".join((title or os.path.splitext(os.path.basename(path))[0]).split())

    sections, skipped = [], 0
    for r in range(header_row + 1, ws.max_row + 1):
        code = _num(ws.cell(r, idx["id"]).value)
        desc = _text(ws.cell(r, idx["desc"]).value)
        if code is None:
            skipped += 1 if desc else 0
            continue
        if code % SECTION_STEP == 0:
            sections.append({"code": str(code), "title": desc or f"Section {code}",
                             "items": []})
        elif sections:
            sections[-1]["items"].append(
                {"item_id": str(code), "review_item": desc,
                 "evidence": _text(ws.cell(r, idx["evid"]).value)})
    wb.close()
    return {"name": name, "sheet": ws.title, "sections": sections, "skipped": skipped,
            "n_items": sum(len(s["items"]) for s in sections)}


def fill(src, dest, values, sheet="", id_col="A", evidence_col="C", status_col="E"):
    """Write a filled copy of the reviewer's workbook.

    `values` maps Issue ID to (status, evidence_text). Status is written
    whenever we have one. Evidence is written only when this app actually holds
    files for the item: an empty answer must not wipe out a note somebody typed
    into the reviewer's sheet by hand.

    Loaded without data_only so formulas and formatting survive the save.
    """
    wb = openpyxl.load_workbook(src)
    ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
    ix, ev, st = _col(id_col), _col(evidence_col), _col(status_col)
    n_status = n_evid = 0
    for r in range(1, ws.max_row + 1):
        code = _num(ws.cell(r, ix).value)
        if code is None or code % SECTION_STEP == 0:
            continue
        status, evidence = values.get(str(code), ("", ""))
        if status:
            ws.cell(r, st).value = status
            n_status += 1
        if evidence:
            ws.cell(r, ev).value = evidence
            n_evid += 1
    wb.save(dest)
    return {"status_written": n_status, "evidence_written": n_evid}


def allowed_statuses(path, sheet="", status_col="E"):
    """The values the workbook's own validation permits in its status column.

    Used to check our mapping against the sheet rather than trusting it: if a
    reviewer reissues the workbook with a different vocabulary, we want to know.
    """
    wb = openpyxl.load_workbook(path)
    ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
    letter = status_col.upper()
    out = []
    for dv in ws.data_validations.dataValidation:
        if dv.type != "list" or not dv.formula1:
            continue
        if not any(str(rng).startswith(letter) for rng in str(dv.sqref).split()):
            continue
        out = [v.strip() for v in str(dv.formula1).strip('"').split(",") if v.strip()]
    wb.close()
    return out
