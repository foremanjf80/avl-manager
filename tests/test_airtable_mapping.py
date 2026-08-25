"""Offline checks on the SQLite -> Airtable mapping.

Runs against the real avl.db, so it catches the failures that actually bite:
a column silently dropped, a stored value that no single-select offers, or a
value that does not survive the encode/decode round trip.

    python -m tests.test_airtable_mapping        # or: pytest tests/
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db
from app.airtable import migrate, schema_map

def _conn():
    return db.conn()

def test_every_column_is_mapped():
    """Nothing in SQLite may be missing from the Airtable spec."""
    c = _conn()
    for spec in schema_map.build(c):
        cols = {r["name"] for r in c.execute(f'PRAGMA table_info("{spec.name}")')}
        mapped = {f.column for f in spec.fields if not f.synthetic}
        assert not cols - mapped, f"{spec.name}: unmapped columns {sorted(cols - mapped)}"
        assert not mapped - cols, f"{spec.name}: mapped phantom columns {sorted(mapped - cols)}"

def test_links_resolve_and_are_ordered():
    """Every link points at a real table that is created before it."""
    c = _conn()
    specs = schema_map.build(c)
    order = [s.name for s in specs]
    for spec in specs:
        for f in spec.links:
            assert f.link in order, f"{spec.name}.{f.column} -> unknown table {f.link}"
            assert order.index(f.link) <= order.index(spec.name), \
                f"{spec.name}.{f.column} -> {f.link} created too late"

def test_primary_field_is_a_legal_primary():
    """Airtable rejects links, checkboxes and dates as the primary field."""
    for spec in schema_map.build(_conn()):
        p = spec.primary_field
        assert p.type == "singleLineText", f"{spec.name}: primary is {p.type}"
        assert p is spec.fields[0], f"{spec.name}: primary is not the first field"
        assert not p.link, f"{spec.name}: primary is a link"

def test_select_choices_cover_stored_values():
    """A single-select that omits a stored value would drop data on push."""
    c = _conn()
    for spec in schema_map.build(c):
        for f in spec.fields:
            if f.type != "singleSelect":
                continue
            offered = {ch["name"] for ch in f.options["choices"]}
            stored = set(schema_map._distinct(c, spec.name, f.column))
            assert not stored - offered, \
                f"{spec.name}.{f.column}: {sorted(stored - offered)} not offered"

def test_values_round_trip():
    """encode() then decode() must preserve every value in the database."""
    c = _conn()
    bad = []
    for spec in schema_map.build(c):
        for row in c.execute(f'SELECT * FROM "{spec.name}"'):
            for f in spec.scalars:
                if f.synthetic:
                    continue
                original = row[f.column]
                sent = migrate.encode(f, original)
                if sent is migrate._SKIP:
                    # Empty in, empty out - nothing to lose.
                    if migrate._normalise(f, original) is not None:
                        bad.append(f"{spec.name}.{f.column}={original!r} dropped")
                    continue
                back = migrate.decode(f, sent)
                if migrate._normalise(f, original) != migrate._normalise(f, back):
                    bad.append(f"{spec.name}.{f.column}: {original!r} -> {sent!r} -> {back!r}")
    assert not bad, "round trip lost data:\n  " + "\n  ".join(bad[:20])

def test_synthetic_keys_are_non_empty():
    """Tables with no name column still need a readable primary value."""
    c = _conn()
    lab = migrate._labels(c)
    for spec in schema_map.build(c):
        if not spec.primary_field.synthetic:
            continue
        for row in c.execute(f'SELECT * FROM "{spec.name}"'):
            key = migrate._key_for(spec.name, row, lab)
            assert key and key.strip(), f"{spec.name}: empty synthesized key"

def test_long_text_fits_airtable_limits():
    """Airtable caps a long-text cell at 100,000 characters."""
    c = _conn()
    for spec in schema_map.build(c):
        for f in spec.scalars:
            if f.type not in ("multilineText", "singleLineText") or f.synthetic:
                continue
            longest = c.execute(
                f'SELECT MAX(LENGTH("{f.column}")) FROM "{spec.name}"').fetchone()[0] or 0
            assert longest <= 100_000, f"{spec.name}.{f.column} is {longest} chars"

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}\n      {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
