"""Builds the Airtable base that mirrors the SQLite schema.

Idempotent: run it against an empty workspace to create the base, or against an
existing base to add whatever db.py has grown since. Tables are created with
their scalar fields first, then link fields are added in a second pass, because
a link cannot be created before the table it points at exists.
"""
from . import config, schema_map

def _table_payload(spec):
    return {"name": spec.name,
            "description": spec.description or None,
            "fields": [f.spec() for f in spec.scalars]}

def _clean(payload):
    return {k: v for k, v in payload.items() if v is not None}

def existing_schema(at, base_id):
    """{table name: {"id": tblId, "fields": {field name: fldId}}}"""
    out = {}
    for t in at.base_schema(base=base_id).get("tables", []):
        out[t["name"]] = {"id": t["id"],
                          "fields": {f["name"]: f["id"] for f in t["fields"]}}
    return out

def provision(at, c, base_id=None, base_name="AVL Manager",
              workspace_id=None, log=print):
    """Create or extend the base. Returns (base_id, {table: tableId})."""
    specs = schema_map.build(c)

    if not base_id:
        workspace_id = workspace_id or config.workspace_id()
        if not workspace_id:
            raise RuntimeError("AIRTABLE_WORKSPACE_ID is required to create a base")
        # create_base needs at least one table, so seed it with the first spec.
        first = specs[0]
        log(f"creating base {base_name!r} with table {first.name}")
        created = at.create_base(base_name, workspace_id,
                                 [_clean(_table_payload(first))])
        base_id = created["id"]
        log(f"  base {base_id}")

    have = existing_schema(at, base_id)

    # Pass 1 - tables and their scalar fields.
    for spec in specs:
        if spec.name in have:
            _add_missing_fields(at, base_id, have, spec, spec.scalars, log)
            continue
        log(f"creating table {spec.name} ({len(spec.scalars)} fields)")
        t = at.create_table(spec.name, [f.spec() for f in spec.scalars],
                            description=spec.description, base=base_id)
        have[spec.name] = {"id": t["id"],
                           "fields": {f["name"]: f["id"] for f in t["fields"]}}

    # Pass 2 - link fields, now that every target table exists.
    for spec in specs:
        for f in spec.links:
            if f.name in have[spec.name]["fields"]:
                continue
            target = have.get(f.link)
            if not target:
                log(f"  ! {spec.name}.{f.name}: target table {f.link} missing")
                continue
            log(f"linking {spec.name}.{f.name} -> {f.link}")
            created = at.create_field(
                have[spec.name]["id"],
                {"name": f.name, "type": "multipleRecordLinks",
                 "options": {"linkedTableId": target["id"]}},
                base=base_id)
            have[spec.name]["fields"][f.name] = created["id"]

    return base_id, {name: meta["id"] for name, meta in have.items()}

def _add_missing_fields(at, base_id, have, spec, fields, log):
    for f in fields:
        if f.name in have[spec.name]["fields"]:
            continue
        log(f"adding {spec.name}.{f.name} ({f.type})")
        created = at.create_field(have[spec.name]["id"], f.spec(), base=base_id)
        have[spec.name]["fields"][f.name] = created["id"]

def diff(at, c, base_id):
    """What the base is missing, and what it has that the mapping does not."""
    specs, have = schema_map.build(c), existing_schema(at, base_id)
    report = {"missing_tables": [], "missing_fields": {}, "extra_fields": {}}
    for spec in specs:
        if spec.name not in have:
            report["missing_tables"].append(spec.name)
            continue
        present = set(have[spec.name]["fields"])
        wanted = {f.name for f in spec.fields}
        if wanted - present:
            report["missing_fields"][spec.name] = sorted(wanted - present)
        # Airtable auto-creates a symmetric field on the far side of every link;
        # those are expected, so only report extras that are not table names.
        extra = {e for e in present - wanted if e not in {s.name for s in specs}}
        if extra:
            report["extra_fields"][spec.name] = sorted(extra)
    return report
