#!/usr/bin/env python3
"""Reset seeded data back to the state the app ships with.

Dry run by default: it prints what it would do and changes nothing. Every
destructive mode takes a timestamped backup of the database first.

    python3 scripts/reset.py                    # report only
    python3 scripts/reset.py --templates        # workstream + IE templates
    python3 scripts/reset.py --work             # clear the work, keep the setup
    python3 scripts/reset.py --fresh            # start completely over

--fresh is the most reliable "base state": the seeders are written to fill an
empty database, so re-seeding from empty is exactly what a new deployment gets.
The narrower modes exist for when you want to keep something.
"""
import argparse, datetime, os, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DB = os.environ.get("AVL_DB", os.path.join(ROOT, "avl.db"))
UPLOADS = os.environ.get("AVL_UPLOADS", os.path.join(ROOT, "data_uploads"))
# Beside the database, not in the checkout: on a deployed box that means the
# backup lands on the same persistent disk rather than in ephemeral code.
BACKUPS = os.path.join(os.path.dirname(os.path.abspath(DB)) or ROOT, "backups")

# What each mode clears, in delete order (children before parents).
WORK_TABLES = ["attachments", "packages", "checklist_items", "actions",
               "call_attendees", "calls", "contacts", "status_history"]
TEMPLATE_TABLES = ["template_revisions", "workstream_template_items", "workstream_templates",
                   "ie_template_revisions", "ie_template_items", "ie_template_sections",
                   "ie_templates"]
IE_WORK_TABLES = ["ie_report_items", "ie_report_sections", "ie_reports"]


def counts(c, tables):
    out = {}
    for t in tables:
        try:
            out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            out[t] = None          # table not created yet
    return out


def backup():
    os.makedirs(BACKUPS, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUPS, f"avl_before_reset_{stamp}.db")
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)            # consistent copy even with WAL in play
    src.close(); dst.close()
    return dest


def report(c):
    print(f"database : {DB}")
    print(f"uploads  : {UPLOADS}")
    print()
    groups = [("templates that would be re-seeded", TEMPLATE_TABLES),
              ("IE reports", IE_WORK_TABLES),
              ("work that would be cleared", WORK_TABLES)]
    for label, tables in groups:
        print(f"  {label}")
        for t, n in counts(c, tables).items():
            print(f"    {t:28} {'-' if n is None else n:>6}")
    keep = ["products", "avls", "listings", "people", "assignments", "users", "audit"]
    print("  kept by --templates and --work")
    for t, n in counts(c, keep).items():
        print(f"    {t:28} {'-' if n is None else n:>6}")
    n_files = len(os.listdir(UPLOADS)) if os.path.isdir(UPLOADS) else 0
    print(f"\n  uploaded files on disk: {n_files}")


def clear(c, tables):
    for t in tables:
        try:
            c.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--templates", action="store_true",
                    help="reset workstream and IE templates to the shipped baselines")
    ap.add_argument("--work", action="store_true",
                    help="clear checklists, packages, IE reports, actions, contacts, calls, files")
    ap.add_argument("--fresh", action="store_true",
                    help="delete the database and uploads entirely; everything re-seeds on next start")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    a = ap.parse_args()

    if not os.path.exists(DB):
        print(f"No database at {DB} - nothing to reset. A new deployment starts at base state.")
        return

    if not (a.templates or a.work or a.fresh):
        c = sqlite3.connect(DB)
        report(c)
        c.close()
        print("\nNothing changed. Re-run with --templates, --work or --fresh.")
        return

    what = []
    if a.fresh:
        what.append("DELETE the database and every uploaded file, then re-seed from empty")
    else:
        if a.templates:
            what.append("delete and re-seed the workstream and IE templates "
                        "(checklists already seeded from them are left alone)")
        if a.work:
            what.append("clear checklists, packages, IE reports, actions, contacts, calls "
                        "and attachments, and delete the uploaded files")
    print("This will:")
    for w in what:
        print(f"  - {w}")
    if not a.yes:
        if input("\nType 'reset' to go ahead: ").strip() != "reset":
            print("Cancelled. Nothing changed.")
            return

    dest = backup()
    print(f"\nBackup written: {dest}")

    if a.fresh:
        os.remove(DB)
        for suffix in ("-wal", "-shm"):
            p = DB + suffix
            if os.path.exists(p):
                os.remove(p)
        if os.path.isdir(UPLOADS):
            shutil.rmtree(UPLOADS)
        os.makedirs(UPLOADS, exist_ok=True)
        print("Database and uploads removed. Start the app and it re-seeds to base state.")
        return

    c = sqlite3.connect(DB)
    c.execute("PRAGMA foreign_keys=ON")
    if a.work:
        clear(c, IE_WORK_TABLES + WORK_TABLES)
        # A checklist row is gone, so nothing may still point at it.
        c.execute("UPDATE actions SET checklist_item_id=NULL, ie_report_id=NULL"
                  if "ie_report_id" in [r[1] for r in c.execute("PRAGMA table_info(actions)")]
                  else "UPDATE actions SET checklist_item_id=NULL")
        c.execute("DELETE FROM meta WHERE key='call_attendees_adopted'")
    if a.templates:
        clear(c, TEMPLATE_TABLES)
        c.execute("UPDATE checklist_items SET template_id=NULL")
        c.execute("UPDATE checklist_items SET ie_report_id=NULL")
    c.commit()
    c.close()

    if a.work and os.path.isdir(UPLOADS):
        shutil.rmtree(UPLOADS)
        os.makedirs(UPLOADS, exist_ok=True)

    # Re-seeding is what init_db does on an empty table, so just run it.
    from app import db
    db.init_db()
    c = sqlite3.connect(DB)
    print("\nAfter reset:")
    report(c)
    c.close()


if __name__ == "__main__":
    main()
