"""CLI for the Airtable backend.

    python -m app.airtable plan                 # show the mapping, no network
    python -m app.airtable provision            # create or extend the base
    python -m app.airtable push [--dry-run]     # SQLite -> Airtable
    python -m app.airtable verify               # compare the two stores
    python -m app.airtable pull --into copy.db  # Airtable -> a SQLite file
    python -m app.airtable diff                 # schema drift
    python -m app.airtable status               # what is configured
"""
import argparse, json, os, sys

def _load_env():
    """Read .env the way the app's run instructions do, without clobbering
    anything already exported."""
    path = os.environ.get("AVL_ENV", ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.split("#")[0].strip())

def _client(base_required=True):
    from .client import Airtable
    from . import config
    config.require("AIRTABLE_PAT")
    if base_required:
        config.require("AIRTABLE_BASE_ID")
    return Airtable()

def cmd_plan(args):
    from .. import db
    from . import schema_map
    c = db.conn()
    specs = schema_map.build(c)
    if args.json:
        print(json.dumps([{"table": s.name, "description": s.description,
                           "fields": [f.spec() | ({"link": f.link} if f.link else {})
                                      for f in s.fields]} for s in specs], indent=2))
        return 0
    for s in specs:
        n = c.execute(f'SELECT COUNT(*) FROM "{s.name}"').fetchone()[0]
        print(f"\n{s.name}  ({n} rows)  - {s.description}")
        for f in s.fields:
            tag = f" -> {f.link}" if f.link else ""
            star = " *primary" if f.primary else ""
            print(f"    {f.column:22s} {f.type}{tag}{star}")
    print(f"\n{len(specs)} tables, "
          f"{sum(len(s.fields) for s in specs)} fields")
    return 0

def cmd_provision(args):
    from .. import db
    from . import config, provision
    at = _client(base_required=False)
    base = args.base or config.base_id() or None
    base_id, tables = provision.provision(
        at, db.conn(), base_id=base, base_name=args.name,
        workspace_id=args.workspace or config.workspace_id())
    print(f"\nbase {base_id} - {len(tables)} tables")
    print(f"Add this to .env:\n  AIRTABLE_BASE_ID={base_id}")
    return 0

def cmd_push(args):
    from .. import db
    from . import migrate
    # A dry run never touches the network, so it must not demand a token.
    at = None if args.dry_run else _client()
    stats = migrate.push(db.conn(), at, tables=args.tables or None,
                         dry_run=args.dry_run)
    total = sum(s["created"] for s in stats.values())
    print(f"\n{total} records created across {len(stats)} tables")
    return 0

def cmd_pull(args):
    from .. import db
    from . import migrate
    os.environ["AVL_DB"] = args.into
    import importlib
    importlib.reload(db)
    db.init_db()
    target = db.conn()
    os.environ["AVL_DB"] = args.source
    importlib.reload(db)
    migrate.pull(_client(), db.conn(), target, tables=args.tables or None)
    print(f"\nwrote {args.into}")
    return 0

def cmd_verify(args):
    from .. import db
    from . import migrate
    report = migrate.verify(db.conn(), _client(), tables=args.tables or None)
    bad = {t: r for t, r in report.items() if r["n_problems"]}
    print(f"\n{len(report) - len(bad)}/{len(report)} tables match")
    if bad:
        print("mismatched: " + ", ".join(sorted(bad)))
    return 1 if bad else 0

def cmd_diff(args):
    from .. import db
    from . import config, provision
    report = provision.diff(_client(), db.conn(), config.base_id())
    print(json.dumps(report, indent=2))
    return 1 if report["missing_tables"] or report["missing_fields"] else 0

def cmd_status(args):
    from . import config
    pat = config.pat()
    print(f"AVL_BACKEND           {config.backend()}")
    print(f"AVL_DB                {os.environ.get('AVL_DB', '(default avl.db)')}")
    print(f"AIRTABLE_PAT          {'set (' + pat[:7] + '...)' if pat else 'NOT SET'}")
    print(f"AIRTABLE_BASE_ID      {config.base_id() or 'NOT SET'}")
    print(f"AIRTABLE_WORKSPACE_ID {config.workspace_id() or 'NOT SET'}")
    print(f"rate limit            {config.rate_limit()} req/s")
    return 0

def main(argv=None):
    _load_env()
    p = argparse.ArgumentParser(prog="python -m app.airtable",
                                description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan", help="show the SQLite -> Airtable mapping")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_plan)

    sp = sub.add_parser("provision", help="create or extend the Airtable base")
    sp.add_argument("--name", default="AVL Manager")
    sp.add_argument("--base", default="", help="extend this base instead of creating one")
    sp.add_argument("--workspace", default="")
    sp.set_defaults(fn=cmd_provision)

    sp = sub.add_parser("push", help="copy SQLite rows into Airtable")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--tables", nargs="*")
    sp.set_defaults(fn=cmd_push)

    sp = sub.add_parser("pull", help="copy Airtable records into a SQLite file")
    sp.add_argument("--into", required=True)
    sp.add_argument("--source", default=os.environ.get("AVL_DB", "avl.db"))
    sp.add_argument("--tables", nargs="*")
    sp.set_defaults(fn=cmd_pull)

    sp = sub.add_parser("verify", help="compare SQLite and Airtable")
    sp.add_argument("--tables", nargs="*")
    sp.set_defaults(fn=cmd_verify)

    sub.add_parser("diff", help="schema drift").set_defaults(fn=cmd_diff)
    sub.add_parser("status", help="show configuration").set_defaults(fn=cmd_status)

    args = p.parse_args(argv)
    return args.fn(args)

if __name__ == "__main__":
    sys.exit(main())
