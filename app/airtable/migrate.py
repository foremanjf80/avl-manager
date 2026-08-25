"""Moves data between SQLite and the Airtable base.

push()   SQLite -> Airtable, in two passes: scalar fields first, then link
         fields, since a link needs the target record to exist already.
pull()   Airtable -> SQLite, rebuilding integer ids from the "id" field each
         record carries.
verify() Compares the two stores field by field and reports what differs.

Airtable has no integer primary keys, so the SQLite id travels as a plain
number field and the recId <-> row id pairing is cached in the local
airtable_ids table. That makes push resumable: a rerun only sends rows that
have not been sent before.
"""
import datetime, json
from . import schema_map

ID_TABLE = """
CREATE TABLE IF NOT EXISTS airtable_ids(
  tbl TEXT NOT NULL, row_id TEXT NOT NULL, record_id TEXT NOT NULL,
  synced_at TEXT NOT NULL, PRIMARY KEY(tbl, row_id));
"""

def ensure_id_table(c):
    c.executescript(ID_TABLE)
    c.commit()

def pk(table):
    """meta is keyed by text; every other table has an INTEGER id."""
    return "key" if table == "meta" else "id"

# ---------------- value coercion ----------------

def _to_date(v):
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None                      # free text in a date-ish column

def _to_datetime(v):
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "")).isoformat() + "Z"
    except ValueError:
        return None

def _to_number(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f

def encode(field, value):
    """SQLite value -> Airtable value. Returns _SKIP when the field is empty."""
    if field.type == "checkbox":
        return bool(_to_number(value))   # 0/1 INTEGER flag
    if value is None or value == "":
        return _SKIP
    if field.type == "number":
        n = _to_number(value)
        return _SKIP if n is None else n
    if field.type == "date":
        d = _to_date(value)
        return _SKIP if d is None else d
    if field.type == "dateTime":
        d = _to_datetime(value)
        return _SKIP if d is None else d
    return str(value)

class _Skip:
    def __repr__(self):
        return "<skip>"
_SKIP = _Skip()

def decode(field, value):
    """Airtable value -> SQLite value."""
    if field.type == "checkbox":
        return 1 if value else 0
    if value is None:
        return None if field.type == "number" else ""
    if field.type == "number":
        return _to_number(value)
    if field.type == "dateTime" and isinstance(value, str):
        # Airtable normalises to ...Z; the app stores naive ISO.
        return value.replace("Z", "").split(".")[0]
    return str(value)

# ---------------- synthesized primary labels ----------------

def _labels(c):
    def m(table, col="name"):
        return {r["id"]: r[col] for r in c.execute(f'SELECT id, {col} FROM "{table}"')}
    return {"products": m("products"), "avls": m("avls"), "people": m("people")}

def _key_for(table, row, lab):
    """A human label for tables with no natural name column."""
    def prod(): return lab["products"].get(row["product_id"], "?")
    def avl():  return lab["avls"].get(row["avl_id"], "?")
    if table == "listings":
        return f"{prod()} x {avl()}"
    if table == "status_history":
        return f"{prod()} x {avl()}: {row['old_status'] or '-'} -> {row['new_status']}"
    if table == "assignments":
        return f"{lab['people'].get(row['person_id'], '?')} - {row['role']}"
    if table == "calls":
        return f"{row['call_date']} {avl()}"
    if table in ("audit", "template_revisions", "ie_template_revisions"):
        return f"{row['ts']} {row['action']}"
    return f"{table}#{row[pk(table)]}"

# ---------------- push ----------------

def _payload(spec, row, lab):
    out = {}
    for f in spec.scalars:
        if f.synthetic:
            out[f.name] = _key_for(spec.name, row, lab)
            continue
        v = encode(f, row[f.column])
        if v is not _SKIP:
            out[f.name] = v
    return out

def _sent_ids(c, table):
    return {r["row_id"] for r in c.execute(
        "SELECT row_id FROM airtable_ids WHERE tbl=?", (table,))}

def _remember(c, table, pairs):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    c.executemany(
        "INSERT OR REPLACE INTO airtable_ids(tbl,row_id,record_id,synced_at) "
        "VALUES(?,?,?,?)", [(table, rid, rec, now) for rid, rec in pairs])
    c.commit()

def id_map(c, table=None):
    """{(table, row_id): recId}"""
    q = "SELECT tbl,row_id,record_id FROM airtable_ids"
    args = ()
    if table:
        q += " WHERE tbl=?"
        args = (table,)
    return {(r["tbl"], r["row_id"]): r["record_id"] for r in c.execute(q, args)}

def push(c, at, tables=None, log=print, dry_run=False):
    """Send every not-yet-sent row, then wire up the links. Resumable."""
    ensure_id_table(c)
    specs = [s for s in schema_map.build(c) if not tables or s.name in tables]
    lab, stats = _labels(c), {}

    for spec in specs:
        rows = list(c.execute(f'SELECT * FROM "{spec.name}"'))
        already = _sent_ids(c, spec.name)
        todo = [r for r in rows if str(r[pk(spec.name)]) not in already]
        stats[spec.name] = {"rows": len(rows), "created": 0,
                            "skipped": len(rows) - len(todo), "linked": 0}
        if not todo:
            log(f"{spec.name:28s} {len(rows):4d} rows, all present")
            continue
        if dry_run:
            log(f"{spec.name:28s} would create {len(todo)} of {len(rows)}")
            continue
        created = at.create_records(spec.name, [_payload(spec, r, lab) for r in todo])
        if len(created) != len(todo):
            raise RuntimeError(
                f"{spec.name}: sent {len(todo)} rows, Airtable returned {len(created)}")
        _remember(c, spec.name,
                  [(str(r[pk(spec.name)]), rec["id"]) for r, rec in zip(todo, created)])
        stats[spec.name]["created"] = len(created)
        log(f"{spec.name:28s} {len(created):4d} created")

    if dry_run:
        return stats

    ids = id_map(c)
    for spec in specs:
        if not spec.links:
            continue
        updates = []
        for row in c.execute(f'SELECT * FROM "{spec.name}"'):
            rec = ids.get((spec.name, str(row[pk(spec.name)])))
            if not rec:
                continue
            fields = {}
            for f in spec.links:
                target = ids.get((f.link, str(row[f.column]))) if row[f.column] else None
                if target:
                    fields[f.name] = [target]
            if fields:
                updates.append({"id": rec, "fields": fields})
        if updates:
            at.update_records(spec.name, updates)
            stats[spec.name]["linked"] = len(updates)
            log(f"{spec.name:28s} {len(updates):4d} linked")
    return stats

# ---------------- pull ----------------

def fetch(at, spec):
    """All records for one table, as {recId: fields}."""
    return {r["id"]: r.get("fields", {}) for r in at.list_records(spec.name)}

def pull(at, c, target, tables=None, log=print):
    """Rebuild SQLite rows from Airtable into an already-initialised target DB."""
    specs = [s for s in schema_map.build(c) if not tables or s.name in tables]
    raw = {s.name: fetch(at, s) for s in specs}
    # recId -> SQLite row id, taken from the id field each record carries.
    back = {rec: fields.get(pk(s.name))
            for s in specs for rec, fields in raw[s.name].items()}
    stats = {}

    for spec in specs:
        cols, vals = [], []
        for f in spec.fields:
            if f.synthetic:
                continue
            cols.append(f.column)
        rows = []
        for rec, fields in raw[spec.name].items():
            row = []
            for f in spec.fields:
                if f.synthetic:
                    continue
                if f.link:
                    linked = fields.get(f.name) or []
                    row.append(back.get(linked[0]) if linked else None)
                else:
                    row.append(decode(f, fields.get(f.name)))
            rows.append(row)
        target.execute(f'DELETE FROM "{spec.name}"')
        target.executemany(
            f'INSERT INTO "{spec.name}" ({",".join(cols)}) '
            f'VALUES ({",".join("?" * len(cols))})', rows)
        stats[spec.name] = len(rows)
        log(f"{spec.name:28s} {len(rows):4d} rows")
    target.commit()
    return stats

# ---------------- verify ----------------

def _normalise(f, v):
    """Compare on meaning, not representation - '' and None are both empty."""
    if f.type == "checkbox":
        return bool(v) if not isinstance(v, (int, float)) else bool(int(v))
    if v in (None, ""):
        return None
    if f.type == "number":
        return _to_number(v)
    if f.type == "date":
        return _to_date(v)
    if f.type == "dateTime":
        return _to_datetime(v)
    return str(v)

def verify(c, at, tables=None, log=print, max_report=10):
    """Field-by-field comparison. Returns {table: {...}} with any mismatches."""
    specs = [s for s in schema_map.build(c) if not tables or s.name in tables]
    ids, report = id_map(c), {}

    for spec in specs:
        local = {str(r[pk(spec.name)]): r for r in c.execute(f'SELECT * FROM "{spec.name}"')}
        remote_by_rec = fetch(at, spec)
        remote = {}
        for rec, fields in remote_by_rec.items():
            key = fields.get(pk(spec.name))
            if key is not None:
                remote[str(key)] = fields

        problems = []
        for missing in sorted(set(local) - set(remote)):
            problems.append(f"row {missing} missing from Airtable")
        for extra in sorted(set(remote) - set(local)):
            problems.append(f"record {extra} not in SQLite")

        for key in sorted(set(local) & set(remote)):
            row, fields = local[key], remote[key]
            for f in spec.scalars:
                if f.synthetic:
                    continue
                want = _normalise(f, row[f.column])
                got = _normalise(f, fields.get(f.name))
                if want != got:
                    problems.append(f"row {key}.{f.column}: {want!r} != {got!r}")
            for f in spec.links:
                want = row[f.column]
                linked = fields.get(f.name) or []
                got = ids.get((f.link, str(want))) if want else None
                if (linked[0] if linked else None) != got:
                    problems.append(f"row {key}.{f.column}: link mismatch")

        report[spec.name] = {"sqlite": len(local), "airtable": len(remote),
                             "problems": problems[:max_report],
                             "n_problems": len(problems)}
        flag = "OK " if not problems else "!! "
        log(f"{flag}{spec.name:28s} sqlite={len(local):4d} airtable={len(remote):4d}"
            + (f"  {len(problems)} problem(s)" if problems else ""))
        for p in problems[:max_report]:
            log(f"     {p}")
    return report
