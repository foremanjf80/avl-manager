"""SQLite data layer for the Qcells AVL Manager."""
import sqlite3, os, datetime

DB_PATH = os.environ.get("AVL_DB", os.path.join(os.path.dirname(__file__), "..", "avl.db"))

STATUSES = ["Listed", "Listed, Conditional", "In Review", "Execution", "Engagement",
            "Opportunity", "No Interest", "No Info", "N/A", "Pre-launch"]

# A conditional listing still counts as on the AVL, but carries conditions that
# have to be met to keep it or to have it lifted - so it is reported separately
# wherever "how many are listed" is being asked.
LISTED_STATUSES = ("Listed", "Listed, Conditional")

ROLES = ["Account Manager (Sales)", "Sr. Commercial Rep (Sales)", "Product/Technical Rep (CE)"]

# Which side of the house someone sits on; drives who appears in each role picker.
# Internal Qcells teams a person can sit in. Not a closed set: anything already
# stored is offered alongside these, and "Other" is defined free-text.
ORGS = ["Sales", "Products / CE", "RBO", "Procurement / Sourcing", "Product Management",
        "Engineering / Technical", "Quality", "Operations", "Supply Chain",
        "Finance", "Legal / Compliance", "Marketing", "IT", "Executive", "Other"]

# Which orgs are conventionally offered first for each trifecta seat. These only
# reorder the Manage pickers - anybody on the roster can still be assigned, since
# an org list can never anticipate every real staffing arrangement.
ORG_ROLE_HINTS = {
    ROLES[0]: ("Sales & account teams", ("Sales", "RBO", "Product Management", "Executive")),
    ROLES[1]: ("Sales & account teams", ("Sales", "RBO", "Product Management", "Executive")),
    ROLES[2]: ("Technical teams", ("Products / CE", "Engineering / Technical", "Quality",
                                   "Product Management")),
}

def orgs_in_use(c):
    """The standard list plus any custom org already saved, so values round-trip."""
    seen = [r["org"] for r in c.execute(
        "SELECT DISTINCT org FROM people WHERE COALESCE(org,'')<>'' ORDER BY org")]
    return ORGS + [o for o in seen if o not in ORGS]

# Orgs that are never offered for a seat, because the pairing does not exist.
# Sales people are not Product/Technical reps; if a technical person sits on
# another team, give them that team on the roster and they show up under "Other
# teams" instead.
ORG_ROLE_EXCLUDE = {
    ROLES[2]: ("Sales",),
}

def role_options(people, role, held_ids=()):
    """Grouped picker options for one seat: [(group label, [people]), ...].

    Anyone already holding the seat is always listed, even if their org is
    excluded, so opening the form can never silently drop them.
    """
    label, hint = ORG_ROLE_HINTS.get(role, ("Suggested", ()))
    excl = ORG_ROLE_EXCLUDE.get(role, ())
    held = set(held_ids)
    suggested = [p for p in people if p["org"] in hint]
    others = [p for p in people if p["org"] not in hint and p["org"] not in excl]
    stale = [p for p in people if p["org"] in excl and p["id"] in held]
    groups = []
    if suggested:
        groups.append((label, suggested))
    if others:
        groups.append(("Other teams", others))
    if stale:
        groups.append(("Currently assigned", stale))
    return groups

def conn():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    # WAL lets readers carry on while someone is saving a form, which is the
    # difference between "fine for one person" and "fine for a team". It is a
    # property of the file, so this is a no-op after the first connection.
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=15000")
    return c

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT,
  role TEXT DEFAULT 'editor', last_login TEXT);
CREATE TABLE IF NOT EXISTS avls(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  account_manager TEXT DEFAULT '', sr_commercial_rep TEXT DEFAULT '',
  notes TEXT DEFAULT '', active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  category TEXT NOT NULL, tech_reps TEXT DEFAULT '',
  launch_status TEXT DEFAULT 'Released', lifecycle TEXT DEFAULT 'Active',
  active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS listings(
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'No Info', note TEXT DEFAULT '',
  updated_by TEXT DEFAULT '', updated_at TEXT DEFAULT '',
  UNIQUE(product_id, avl_id));
CREATE TABLE IF NOT EXISTS calls(
  id INTEGER PRIMARY KEY,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  call_date TEXT NOT NULL, call_type TEXT DEFAULT 'Joint',
  qcells_attendees TEXT DEFAULT '', tpo_attendees TEXT DEFAULT '',
  topics TEXT DEFAULT '', outcomes TEXT DEFAULT '',
  owner_due TEXT DEFAULT '', created_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS status_history(
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  old_status TEXT, new_status TEXT NOT NULL,
  changed_by TEXT, ts TEXT NOT NULL, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS people(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, email TEXT DEFAULT '',
  org TEXT DEFAULT '', active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS assignments(
  id INTEGER PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  avl_id INTEGER REFERENCES avls(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
  started_at TEXT NOT NULL, ended_at TEXT,
  added_by TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY,
  avl_id INTEGER REFERENCES avls(id) ON DELETE CASCADE,
  call_id INTEGER REFERENCES calls(id) ON DELETE SET NULL,
  description TEXT NOT NULL, owner TEXT DEFAULT '', due_date TEXT DEFAULT '',
  status TEXT DEFAULT 'Open', created_by TEXT, created_at TEXT, closed_at TEXT);
CREATE TABLE IF NOT EXISTS checklist_items(
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  workstream TEXT NOT NULL, status TEXT DEFAULT 'Not Started', pct TEXT DEFAULT '',
  eta TEXT DEFAULT '', owner TEXT DEFAULT '', notes TEXT DEFAULT '',
  updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS attachments(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, ref_id INTEGER NOT NULL,
  filename TEXT NOT NULL, stored_path TEXT NOT NULL,
  uploaded_by TEXT, uploaded_at TEXT);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, user_email TEXT,
  action TEXT NOT NULL, detail TEXT);
"""

SEED_AVLS = [
    # name, account_manager
    ("EnFin", "TBD"),
    ("Sunrun", "Sarah Gaddis"),
    ("Palmetto LightReach", "Carrie Ford"),
    ("GoodLeap", "Carrie Ford"),
    ("Skylight Lending", "Carrie Ford"),
    ("IGS Energy", "Sarah Gaddis"),
    ("Participate Energy", "Sarah Gaddis"),
    ("HDM Renewable Finance", "Sarah Gaddis"),
    ("EverBright", ""),
    ("PosiGen", ""),
    ("Solrite", ""),
    ("Base Power", ""),
]

SEED_PRODUCTS = [
    # name, category, tech_reps, launch_status
    ("Q.PEAK DUO BLK ML-G10.C+", "DC Module", "", "Released"),
    ("Q.TRON BLK M G2.C+", "DC Module", "", "Released"),
    ("Q.TRON BLK M-G2.H+", "DC Module", "", "Released"),
    ("Q.PEAK DUO BLK ML G10.C1+/AC", "AC Module", "John Foreman + Sarah O.", "Released"),
    ("Q.TRON BLK M G2.C1+/AC", "AC Module", "John Foreman + Sarah O.", "Released"),
    ("Q.TRON BLK M G2.H1+/AC", "AC Module", "John Foreman + Sarah O.", "Released"),
    ("G3 ESS", "ESS", "", "Released"),
    ("G3 ESS DCA", "ESS", "", "Released"),
    ("Q.MI Gen2", "MLPE", "John Foreman + Sarah O.", "Q4-26"),
    ("Gen4 ESS (Omnia OPTI G2)", "ESS", "John Foreman + Lino Jang", "In dataroom"),
    ("ML-G12S.3/BGH (hail)", "DC Module", "", "Q1-27"),
    ("XL-G2R/BFG", "DC Module", "", "Q1-28"),
]

# Aug-2026 AVL Status slide, columns in SEED_AVLS order for the first 8 AVLs.
SEED_STATUS = {
    "Q.PEAK DUO BLK ML-G10.C+":     ["Listed"]*8,
    "Q.TRON BLK M G2.C+":           ["Listed","Listed","Listed","In Review","Listed","Listed","Listed","Listed"],
    "Q.TRON BLK M-G2.H+":           ["Listed","Listed","N/A","Listed","Listed","Listed","Listed","Listed"],
    "Q.PEAK DUO BLK ML G10.C1+/AC": ["Listed","No Interest","Listed","Execution","Execution","No Interest","Listed","Listed"],
    "Q.TRON BLK M G2.C1+/AC":       ["Listed","No Interest","Listed","In Review","Execution","No Interest","Listed","Listed"],
    "Q.TRON BLK M G2.H1+/AC":       ["Listed","No Interest","N/A","Listed","N/A","No Interest","Listed","N/A"],
    "G3 ESS":                       ["Listed","N/A","N/A","N/A","N/A","N/A","In Review","In Review"],
    "G3 ESS DCA":                   ["Listed","No Info","Engagement","Execution","Execution","No Info","In Review","In Review"],
}

def _migrate(c):
    cols = [r[1] for r in c.execute("PRAGMA table_info(products)")]
    if "lifecycle" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN lifecycle TEXT DEFAULT 'Active'")
        c.execute("UPDATE products SET lifecycle = CASE WHEN launch_status='Released' "
                  "THEN 'Active' ELSE 'Roadmap' END")
        c.commit()
    ck = [r[1] for r in c.execute("PRAGMA table_info(checklist_items)")]
    if "sort_order" not in ck:
        c.execute("ALTER TABLE checklist_items ADD COLUMN sort_order INTEGER DEFAULT 0")
        c.execute("UPDATE checklist_items SET sort_order = id")
        c.commit()
    if "template_id" not in ck:
        c.execute("ALTER TABLE checklist_items ADD COLUMN template_id INTEGER")
        c.commit()
    # eta was free text ("End Aug"), so nothing could be flagged late. Keep it for
    # the loose case and add a real date beside it.
    if "due_date" not in ck:
        c.execute("ALTER TABLE checklist_items ADD COLUMN due_date TEXT DEFAULT ''")
        c.commit()
    # The IE report is itself a line item on every AVL dataroom, so a requirement
    # can point at the review that answers it and read its progress live.
    if "ie_report_id" not in ck:
        c.execute("ALTER TABLE checklist_items ADD COLUMN ie_report_id INTEGER")
        c.commit()
    # Requirement rows carry the tracker's Document Category and obligation.
    for col, ddl in (("doc_category", "TEXT DEFAULT ''"),
                     ("obligation", "TEXT DEFAULT 'Required'")):
        if col not in ck:
            c.execute(f"ALTER TABLE checklist_items ADD COLUMN {col} {ddl}")
            c.commit()
    ti = [r[1] for r in c.execute("PRAGMA table_info(workstream_template_items)")]
    for col, ddl in (("doc_category", "TEXT DEFAULT ''"),
                     ("obligation", "TEXT DEFAULT 'Required'")):
        if ti and col not in ti:
            c.execute(f"ALTER TABLE workstream_template_items ADD COLUMN {col} {ddl}")
            c.commit()
    li = [r[1] for r in c.execute("PRAGMA table_info(listings)")]
    # A listing is the outcome; these turn it into a tracked pursuit. Deliberately
    # not a second phase enum - status already says where it stands.
    for col, ddl in (("owner", "TEXT DEFAULT ''"), ("owner_person_id", "INTEGER"),
                     ("target_date", "TEXT DEFAULT ''"), ("submitted_at", "TEXT DEFAULT ''"),
                     ("condition", "TEXT DEFAULT ''"), ("next_milestone", "TEXT DEFAULT ''"),
                     ("risk", "TEXT DEFAULT ''"), ("priority", "TEXT DEFAULT 'Normal'")):
        if col not in li:
            c.execute(f"ALTER TABLE listings ADD COLUMN {col} {ddl}")
            c.commit()
    au = [r[1] for r in c.execute("PRAGMA table_info(audit)")]
    # Free-text detail alone cannot be filtered by TPO or product, which is what
    # made the audit log unusable. Events carry their subject from here on.
    for col, ddl in (("avl_id", "INTEGER"), ("product_id", "INTEGER"),
                     ("entity", "TEXT DEFAULT ''"), ("entity_id", "INTEGER")):
        if col not in au:
            c.execute(f"ALTER TABLE audit ADD COLUMN {col} {ddl}")
            c.commit()
    if "ix_audit_ts" not in [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")]:
        c.execute("CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit(ts DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_audit_avl ON audit(avl_id, product_id)")
        c.commit()
    pk = [r[1] for r in c.execute("PRAGMA table_info(packages)")]
    # Packages get a revision number and code so a TPO can be told exactly which
    # cut they are looking at.
    for col, ddl in (("revision", "INTEGER DEFAULT 1"), ("rev_code", "TEXT DEFAULT ''"),
                     ("rev_date", "TEXT DEFAULT ''"), ("template_id", "INTEGER"),
                     ("n_untracked", "INTEGER DEFAULT 0"), ("superseded", "INTEGER DEFAULT 0")):
        if pk and col not in pk:
            c.execute(f"ALTER TABLE packages ADD COLUMN {col} {ddl}")
            c.commit()
    ac = [r[1] for r in c.execute("PRAGMA table_info(actions)")]
    # Actions gain a roster-backed owner and an optional link to the requirement
    # they unblock.
    for col, ddl in (("owner_person_id", "INTEGER"), ("product_id", "INTEGER"),
                     ("checklist_item_id", "INTEGER"), ("priority", "TEXT DEFAULT 'Normal'")):
        if col not in ac:
            c.execute(f"ALTER TABLE actions ADD COLUMN {col} {ddl}")
            c.commit()
    tt = [r[1] for r in c.execute("PRAGMA table_info(workstream_templates)")]
    if tt and "source_url" not in tt:
        c.execute("ALTER TABLE workstream_templates ADD COLUMN source_url TEXT DEFAULT ''")
        c.commit()
    irs = [r[1] for r in c.execute("PRAGMA table_info(ie_report_sections)")]
    # Long-form response text drafted per section of a live review. Lives on the
    # report, not the template: it is this product's answer, not the question.
    if irs and "narrative" not in irs:
        c.execute("ALTER TABLE ie_report_sections ADD COLUMN narrative TEXT DEFAULT ''")
        c.commit()

def _seed_team(c):
    if c.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]:
        return
    import datetime as _dt
    now = _dt.datetime.now().isoformat(timespec="seconds")
    def person(name, org=""):
        c.execute("INSERT OR IGNORE INTO people(name, org) VALUES(?,?)", (name, org))
        return c.execute("SELECT id FROM people WHERE name=?", (name,)).fetchone()["id"]
    def avl_id(name):
        r = c.execute("SELECT id FROM avls WHERE name=?", (name,)).fetchone()
        return r["id"] if r else None
    def prod_id(name):
        r = c.execute("SELECT id FROM products WHERE name LIKE ?", (name+"%",)).fetchone()
        return r["id"] if r else None
    AM, SCR, PT = ROLES
    sarah_g = person("Sarah Gaddis", "Sales"); carrie = person("Carrie Ford", "Sales")
    john = person("John Foreman", "Products / CE"); sarah_o = person("Sarah O.", "Products / CE")
    lino = person("Lino Jang", "Products / CE")
    for a in ("Sunrun", "IGS Energy", "Participate Energy", "HDM Renewable Finance"):
        if avl_id(a): c.execute("INSERT INTO assignments(person_id, role, avl_id, started_at, added_by) VALUES(?,?,?,?, 'seed')", (sarah_g, AM, avl_id(a), now))
    for a in ("Palmetto LightReach", "GoodLeap", "Skylight Lending"):
        if avl_id(a): c.execute("INSERT INTO assignments(person_id, role, avl_id, started_at, added_by) VALUES(?,?,?,?, 'seed')", (carrie, AM, avl_id(a), now))
    for pn in ("Q.PEAK DUO BLK ML G10.C1+/AC", "Q.TRON BLK M G2.C1+/AC", "Q.TRON BLK M G2.H1+/AC", "Q.MI Gen2"):
        pid = prod_id(pn)
        if pid:
            for who in (john, sarah_o):
                c.execute("INSERT INTO assignments(person_id, role, product_id, started_at, added_by) VALUES(?,?,?,?, 'seed')", (who, PT, pid, now))
    pid = prod_id("Gen4 ESS")
    if pid:
        for who in (john, lino):
            c.execute("INSERT INTO assignments(person_id, role, product_id, started_at, added_by) VALUES(?,?,?,?, 'seed')", (who, PT, pid, now))
    c.commit()

def init_db():
    c = conn()
    c.executescript(SCHEMA)
    c.executescript(EXTRA_SCHEMA)
    c.executescript(IE_SCHEMA)
    _migrate(c)
    if c.execute("SELECT COUNT(*) FROM avls").fetchone()[0] == 0:
        for name, am in SEED_AVLS:
            c.execute("INSERT INTO avls(name, account_manager) VALUES(?,?)", (name, am))
        for name, cat, reps, launch in SEED_PRODUCTS:
            lifecycle = "Active" if launch == "Released" else "Roadmap"
            c.execute("INSERT INTO products(name, category, tech_reps, launch_status, lifecycle) "
                      "VALUES(?,?,?,?,?)", (name, cat, reps, launch, lifecycle))
        avl_ids = {r["name"]: r["id"] for r in c.execute("SELECT id, name FROM avls")}
        prod_ids = {r["name"]: r["id"] for r in c.execute("SELECT id, name FROM products")}
        first8 = [n for n, _ in SEED_AVLS[:8]]
        now = datetime.datetime.now().isoformat(timespec="seconds")
        for pname, pid in prod_ids.items():
            for aname, aid in avl_ids.items():
                if pname in SEED_STATUS and aname in first8:
                    status = SEED_STATUS[pname][first8.index(aname)]
                elif pname in SEED_STATUS:
                    status = "No Info"
                else:
                    status = "Pre-launch"
                c.execute("INSERT INTO listings(product_id, avl_id, status, updated_by, updated_at) VALUES(?,?,?,?,?)",
                          (pid, aid, status, "seed:Aug-2026 AVL Status slide", now))
        c.execute("INSERT INTO audit(ts, user_email, action, detail) VALUES(?,?,?,?)",
                  (now, "system", "seed", "Database seeded from Aug-2026 AVL Status slide"))
        c.commit()
    # These need the AVLs and products to exist first.
    _seed_team(c)
    _seed_workstream_templates(c)
    _adopt_freetext_reps(c)
    _adopt_call_attendees(c)
    _adopt_action_owners(c)
    _seed_ie(c)
    _backfill_audit_subjects(c)
    c.close()

def log(user_email, action, detail="", avl_id=None, product_id=None,
        entity="", entity_id=None):
    c = conn()
    c.execute("INSERT INTO audit(ts, user_email, action, detail, avl_id, product_id, "
              "entity, entity_id) VALUES(?,?,?,?,?,?,?,?)",
              (datetime.datetime.now().isoformat(timespec="seconds"), user_email, action,
               detail, avl_id, product_id, entity, entity_id))
    c.commit(); c.close()


# ---------------- activity feed (v25) ----------------
# One stream over the audit log and the listing changelog. Status changes live in
# their own table because they carry from/to, so they are merged in rather than
# duplicated into audit.
PURSUIT_PRIORITIES = ["High", "Normal", "Low"]

ACTIVITY_TYPES = {
    "status":     ("Listing status", ("status", "listing")),
    "dataroom":   ("Dataroom", ("dataroom",)),
    "package":    ("Packages", ("package",)),
    "ie":         ("DNV / IE", ("ie",)),
    "workstream": ("Templates", ("workstream",)),
    "file":       ("Files", ("file", "files")),
    "action":     ("Actions", ("action",)),
    "call":       ("Calls", ("call",)),
    "contact":    ("Contacts", ("contact",)),
    "people":     ("Team", ("person", "assign", "product", "avl")),
    "admin":      ("Admin", ("role", "backup", "seed", "migrate")),
}

def activity_type(action):
    head = (action or "").split(":")[0]
    for key, (_lbl, prefixes) in ACTIVITY_TYPES.items():
        if head in prefixes:
            return key
    return "admin"

def _backfill_audit_subjects(c):
    """Best effort: match older free-text detail against known AVL / product names.

    Only fills rows that have no subject yet, and only on an unambiguous single
    match, so it can never invent a wrong attribution.
    """
    if c.execute("SELECT value FROM meta WHERE key='audit_backfilled'").fetchone():
        return
    avls = [(r["id"], r["name"]) for r in c.execute("SELECT id, name FROM avls")]
    prods = [(r["id"], r["name"]) for r in c.execute("SELECT id, name FROM products")]
    for r in c.execute("SELECT id, detail FROM audit WHERE avl_id IS NULL AND product_id IS NULL "
                       "AND COALESCE(detail,'')<>''").fetchall():
        d = r["detail"]
        a = [i for i, n in avls if n and n in d]
        p = [i for i, n in prods if n and n in d]
        if len(a) == 1 or len(p) == 1:
            c.execute("UPDATE audit SET avl_id=?, product_id=? WHERE id=?",
                      (a[0] if len(a) == 1 else None, p[0] if len(p) == 1 else None, r["id"]))
    c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('audit_backfilled', ?)",
              (datetime.datetime.now().isoformat(timespec="seconds"),))
    c.commit()


WORKSTREAMS = ["DNV / Bankability (IE)", "Certification & Standards", "3rd Party Validation (RETC/PVEL)",
               "Beta & Field Validation", "Factory Quality & Audit", "Design Tools / Software",
               "API + Cybersecurity", "BOM Change Control & Re-qual",
               "Tax Credit & Trade Compliance", "Commercial & Warranty Terms", "Corporate & Vendor Diligence"]
CHECK_STATUSES = ["Not Started", "In Progress", "Blocked", "Complete", "Submitted", "Accepted", "TBD"]

# "Complete" means we hold the document; "Submitted" that it has gone to the TPO;
# "Accepted" that they have taken it. All three count as done on our side.
CHECK_DONE = ("Complete", "Submitted", "Accepted")


# ---------------- workstream templates (v7) ----------------
# Product categories the matrix understands. Templates are scoped by category so a
# PV module dataroom no longer inherits the ESS workstream list.
CATEGORIES = ["DC Module", "AC Module", "MLPE", "Inverter", "ESS", "Smart Panel", "Other"]

# How binding a requirement is, straight from the "Required or Optional" column
# of the EnFin trackers.
OBLIGATIONS = ["Required", "Conditional", "Optional"]

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS workstream_templates(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
  category TEXT DEFAULT '',
  avl_id INTEGER REFERENCES avls(id) ON DELETE CASCADE,
  notes TEXT DEFAULT '', source_url TEXT DEFAULT '', active INTEGER DEFAULT 1,
  created_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS workstream_template_items(
  id INTEGER PRIMARY KEY,
  template_id INTEGER NOT NULL REFERENCES workstream_templates(id) ON DELETE CASCADE,
  doc_category TEXT DEFAULT '', workstream TEXT NOT NULL,
  obligation TEXT DEFAULT 'Required', description TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_wti_template ON workstream_template_items(template_id);
CREATE INDEX IF NOT EXISTS ix_checklist_pa ON checklist_items(product_id, avl_id);
CREATE INDEX IF NOT EXISTS ix_attach_kind ON attachments(kind, ref_id);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS commitments(
  id INTEGER PRIMARY KEY,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  kind TEXT DEFAULT 'Dataroom submission', label TEXT DEFAULT '',
  due_date TEXT NOT NULL, owner TEXT DEFAULT '',
  owner_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
  status TEXT DEFAULT 'Planned', met_at TEXT DEFAULT '', notes TEXT DEFAULT '',
  created_by TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_commit_due ON commitments(status, due_date);
CREATE INDEX IF NOT EXISTS ix_commit_pa ON commitments(avl_id, product_id);
CREATE TABLE IF NOT EXISTS contacts(
  id INTEGER PRIMARY KEY,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  name TEXT NOT NULL, role TEXT DEFAULT '', email TEXT DEFAULT '',
  phone TEXT DEFAULT '', website TEXT DEFAULT '', notes TEXT DEFAULT '',
  is_primary INTEGER DEFAULT 0, active INTEGER DEFAULT 1,
  created_by TEXT, created_at TEXT, updated_by TEXT, updated_at TEXT);
CREATE INDEX IF NOT EXISTS ix_contacts_avl ON contacts(avl_id, active);
CREATE TABLE IF NOT EXISTS packages(
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  avl_id INTEGER NOT NULL REFERENCES avls(id) ON DELETE CASCADE,
  label TEXT DEFAULT '', scope TEXT DEFAULT 'all',
  n_files INTEGER DEFAULT 0, n_reqs INTEGER DEFAULT 0, n_gaps INTEGER DEFAULT 0,
  bytes INTEGER DEFAULT 0, stored_path TEXT DEFAULT '', manifest TEXT DEFAULT '',
  created_by TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_packages_pa ON packages(product_id, avl_id);
CREATE TABLE IF NOT EXISTS call_attendees(
  id INTEGER PRIMARY KEY,
  call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
  side TEXT NOT NULL,                 -- 'qcells' | 'tpo'
  person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
  contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
  name TEXT NOT NULL);                -- kept so history survives a delete
CREATE INDEX IF NOT EXISTS ix_call_att ON call_attendees(call_id, side);
CREATE TABLE IF NOT EXISTS template_revisions(
  id INTEGER PRIMARY KEY,
  template_id INTEGER NOT NULL REFERENCES workstream_templates(id) ON DELETE CASCADE,
  action TEXT NOT NULL, detail TEXT DEFAULT '',
  snapshot TEXT NOT NULL,              -- JSON of the template as it was BEFORE the change
  actor TEXT, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_trev ON template_revisions(template_id, id DESC);
"""

# Starter template library, imported from the EnFin AVL Requirements Trackers.
# See app/seed_workstreams.py for the data and the source sheet for each one.
SEED_TAG = "seed:enfin-2026-06"

def _seed_workstream_templates(c):
    from .seed_workstreams import TEMPLATES, SRC
    if c.execute("SELECT COUNT(*) FROM workstream_templates WHERE created_by=?",
                 (SEED_TAG,)).fetchone()[0]:
        return
    now = datetime.datetime.now().isoformat(timespec="seconds")
    # Retire the earlier hand-written starter set, but never touch one that has
    # already seeded a live checklist or that somebody has edited.
    c.execute("DELETE FROM workstream_templates WHERE created_by='seed' "
              "AND id NOT IN (SELECT DISTINCT template_id FROM checklist_items "
              "WHERE template_id IS NOT NULL)")
    for name, cat, sheet_id, items in TEMPLATES:
        if c.execute("SELECT 1 FROM workstream_templates WHERE name=?", (name,)).fetchone():
            continue
        c.execute("INSERT INTO workstream_templates(name, category, avl_id, notes, source_url, "
                  "created_by, created_at) VALUES(?,?,NULL,?,?,?,?)",
                  (name, cat, "Imported from the EnFin AVL Requirements Tracker (Jun 2026).",
                   SRC.format(sheet_id), SEED_TAG, now))
        tid = c.execute("SELECT id FROM workstream_templates WHERE name=?", (name,)).fetchone()["id"]
        for i, (doc_cat, req, obligation, note) in enumerate(items):
            c.execute("INSERT INTO workstream_template_items(template_id, doc_category, workstream, "
                      "obligation, description, sort_order) VALUES(?,?,?,?,?,?)",
                      (tid, doc_cat, req, obligation, note, i))
    c.commit()

def templates_for(c, category="", avl_id=None):
    """Templates usable for a category x AVL, best match first.

    Precedence: exact category+AVL, then category-only, then any-category+AVL,
    then the fully generic ones. Inactive templates are excluded.
    """
    rows = c.execute("SELECT t.*, (SELECT COUNT(*) FROM workstream_template_items i "
                     "WHERE i.template_id=t.id) AS n_items, a.name AS avl_name "
                     "FROM workstream_templates t LEFT JOIN avls a ON a.id=t.avl_id "
                     "WHERE t.active=1 AND (t.category='' OR t.category=?) "
                     "AND (t.avl_id IS NULL OR t.avl_id=?) ",
                     (category or "", avl_id)).fetchall()
    def rank(r):
        return (0 if (r["category"] and r["avl_id"]) else
                1 if r["category"] else
                2 if r["avl_id"] else 3)
    return sorted(rows, key=lambda r: (rank(r), r["name"]))


# ---------------- roster-driven assignments (v9) ----------------
# Assignments are the single source of truth for who covers what. The free-text
# columns on products/avls are kept as a denormalised cache so the dashboard and
# exports can render names without a join.

def role_holders(c, role, avl_id=None, product_id=None):
    """Open assignments for one role on one AVL *or* one product.

    Deliberately ignores combined product-at-AVL assignments: those are the
    finer-grained ones made on the Team page and Manage must not silently drop them.
    """
    if avl_id is not None:
        q = ("SELECT a.id, a.person_id, p.name FROM assignments a JOIN people p ON p.id=a.person_id "
             "WHERE a.role=? AND a.avl_id=? AND a.product_id IS NULL AND a.ended_at IS NULL "
             "ORDER BY p.name")
        args = (role, avl_id)
    else:
        q = ("SELECT a.id, a.person_id, p.name FROM assignments a JOIN people p ON p.id=a.person_id "
             "WHERE a.role=? AND a.product_id=? AND a.avl_id IS NULL AND a.ended_at IS NULL "
             "ORDER BY p.name")
        args = (role, product_id)
    return c.execute(q, args).fetchall()

def set_role_holders(c, role, person_ids, avl_id=None, product_id=None, actor=""):
    """Make the open assignments for a role match `person_ids` exactly.

    Removals end the assignment (history is retained, never deleted). Unknown or
    deactivated people are ignored rather than assigned.
    """
    cur = {r["person_id"]: r for r in role_holders(c, role, avl_id, product_id)}
    want = {int(p) for p in person_ids if str(p).strip()}
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    added, removed = [], []
    for pid, r in cur.items():
        if pid not in want:
            c.execute("UPDATE assignments SET ended_at=? WHERE id=?", (ts, r["id"]))
            removed.append(r["name"])
    for pid in want - set(cur):
        row = c.execute("SELECT name FROM people WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            continue
        c.execute("INSERT INTO assignments(person_id, role, avl_id, product_id, started_at, added_by) "
                  "VALUES(?,?,?,?,?,?)", (pid, role, avl_id, product_id, ts, actor))
        added.append(row["name"])
    return added, removed

def refresh_rep_cache(c, avl_id=None, product_id=None):
    """Rewrite the legacy name columns from the current assignments."""
    AM, SCR, PT = ROLES
    if avl_id is not None:
        c.execute("UPDATE avls SET account_manager=?, sr_commercial_rep=? WHERE id=?",
                  (", ".join(r["name"] for r in role_holders(c, AM, avl_id=avl_id)),
                   ", ".join(r["name"] for r in role_holders(c, SCR, avl_id=avl_id)),
                   avl_id))
    if product_id is not None:
        c.execute("UPDATE products SET tech_reps=? WHERE id=?",
                  (", ".join(r["name"] for r in role_holders(c, PT, product_id=product_id)),
                   product_id))

def refresh_all_rep_caches(c):
    for r in c.execute("SELECT id FROM avls").fetchall():
        refresh_rep_cache(c, avl_id=r["id"])
    for r in c.execute("SELECT id FROM products").fetchall():
        refresh_rep_cache(c, product_id=r["id"])

def _adopt_freetext_reps(c):
    """One-time: turn the typed-in names on products/avls into real people + assignments.

    Runs once so nothing that was hand-entered before the roster existed is lost.
    A name that matches an existing person (case-insensitively) reuses that person.
    """
    if c.execute("SELECT value FROM meta WHERE key='reps_adopted'").fetchone():
        return
    AM, SCR, PT = ROLES
    ts = datetime.datetime.now().isoformat(timespec="seconds")

    def norm(n):
        # "Sarah O." and "Sarah O" are the same person.
        return n.strip().rstrip(".").lower()

    existing = {norm(r["name"]): r["id"] for r in c.execute("SELECT id, name FROM people")}

    def person(name, org):
        pid = existing.get(norm(name))
        if pid:
            c.execute("UPDATE people SET active=1 WHERE id=?", (pid,))
            return pid
        c.execute("INSERT INTO people(name, org) VALUES(?,?)", (name, org))
        pid = c.execute("SELECT id FROM people WHERE name=?", (name,)).fetchone()["id"]
        existing[norm(name)] = pid
        return pid

    def names(raw):
        # "John Foreman + Sarah O." / "A, B" / "A & B" -> ["John Foreman", "Sarah O."]
        out = []
        for part in _re_split(raw or ""):
            n = part.strip()
            if n and n.upper().rstrip(".") not in ("TBD", "N/A", "NA", "-"):
                out.append(n)
        return out

    for r in c.execute("SELECT id, account_manager, sr_commercial_rep FROM avls").fetchall():
        for role, raw in ((AM, r["account_manager"]), (SCR, r["sr_commercial_rep"])):
            want = [person(n, "Sales") for n in names(raw)]
            if want:
                set_role_holders(c, role, want, avl_id=r["id"], actor="migrate:free-text")
    for r in c.execute("SELECT id, tech_reps FROM products").fetchall():
        want = [person(n, "Products / CE") for n in names(r["tech_reps"])]
        if want:
            set_role_holders(c, PT, want, product_id=r["id"], actor="migrate:free-text")

    refresh_all_rep_caches(c)
    c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('reps_adopted', ?)", (ts,))
    c.commit()

def _re_split(raw):
    import re
    return [p for p in re.split(r"\s*(?:\+|&|,|/| and )\s*", raw) if p.strip()]


# ---------------- TPO-side contacts (v10) ----------------
# These are the people at the TPO, not the Qcells roster in `people`. Roles are a
# suggestion list rather than a fixed set: every financier titles these differently.
CONTACT_ROLES = ["Procurement / Sourcing", "Product Management", "Engineering / Technical",
                 "Quality", "Operations", "Sales / Account Management", "Finance",
                 "Legal / Compliance", "Executive", "Other"]

def normalize_website(url):
    """Accept 'example.com' and store something a browser can actually follow."""
    u = (url or "").strip()
    if u and not u.lower().startswith(("http://", "https://")):
        u = "https://" + u
    return u


# ---------------- dataroom packages (v11) ----------------
# What a submission to a TPO may contain. The manifest always lists everything in
# scope so gaps are visible; only requirements that actually have files get folders.
PACKAGE_SCOPES = {
    "all": "Every requirement",
    "required": "Required only",
    "req_cond": "Required + Conditional",
}

def scope_filter(scope):
    """SQL fragment + params limiting checklist rows to a package scope."""
    if scope == "required":
        return "AND obligation='Required' ", []
    if scope == "req_cond":
        return "AND obligation IN ('Required','Conditional') ", []
    return "", []


# ---------------- call attendees (v12) ----------------
# Attendees are picked from the Qcells roster and the TPO contact list, with a
# free-text field for one-off guests. The names stay denormalised onto calls so
# the CSV export and weekly digest keep working unchanged.
CALL_TYPES = ["Joint", "Technical", "Commercial", "Intro", "QBR", "Escalation", "Site visit"]

def call_attendees(c, call_id):
    rows = c.execute("SELECT * FROM call_attendees WHERE call_id=? ORDER BY side, name",
                     (call_id,)).fetchall()
    out = {"qcells": [], "tpo": []}
    for r in rows:
        out.setdefault(r["side"], []).append(r)
    return out

def set_call_attendees(c, call_id, side, person_ids=(), contact_ids=(), other=""):
    """Replace one side's attendee list and refresh the cached name string."""
    c.execute("DELETE FROM call_attendees WHERE call_id=? AND side=?", (call_id, side))
    for pid in person_ids:
        row = c.execute("SELECT name FROM people WHERE id=?", (pid,)).fetchone()
        if row:
            c.execute("INSERT INTO call_attendees(call_id, side, person_id, name) VALUES(?,?,?,?)",
                      (call_id, side, pid, row["name"]))
    for cid in contact_ids:
        row = c.execute("SELECT name FROM contacts WHERE id=?", (cid,)).fetchone()
        if row:
            c.execute("INSERT INTO call_attendees(call_id, side, contact_id, name) VALUES(?,?,?,?)",
                      (call_id, side, cid, row["name"]))
    for nm in _re_split(other or ""):
        nm = nm.strip()
        if nm:
            c.execute("INSERT INTO call_attendees(call_id, side, name) VALUES(?,?,?)",
                      (call_id, side, nm))
    names = [r["name"] for r in c.execute(
        "SELECT name FROM call_attendees WHERE call_id=? AND side=? ORDER BY name",
        (call_id, side))]
    col = "qcells_attendees" if side == "qcells" else "tpo_attendees"
    c.execute(f"UPDATE calls SET {col}=? WHERE id=?", (", ".join(names), call_id))

def _adopt_call_attendees(c):
    """One-time: parse the free-text attendee strings into structured rows."""
    if c.execute("SELECT value FROM meta WHERE key='call_attendees_adopted'").fetchone():
        return
    people = {r["name"].strip().rstrip(".").lower(): r["id"]
              for r in c.execute("SELECT id, name FROM people")}
    for call in c.execute("SELECT id, avl_id, qcells_attendees, tpo_attendees FROM calls").fetchall():
        contacts = {r["name"].strip().lower(): r["id"] for r in c.execute(
            "SELECT id, name FROM contacts WHERE avl_id=?", (call["avl_id"],))}
        for side, raw, lookup in (("qcells", call["qcells_attendees"], people),
                                  ("tpo", call["tpo_attendees"], contacts)):
            pids, cids, rest = [], [], []
            for nm in _re_split(raw or ""):
                key = nm.strip().rstrip(".").lower()
                if side == "qcells" and key in lookup:
                    pids.append(lookup[key])
                elif side == "tpo" and key in lookup:
                    cids.append(lookup[key])
                elif nm.strip():
                    rest.append(nm.strip())
            if pids or cids or rest:
                set_call_attendees(c, call["id"], side, pids, cids, ", ".join(rest))
    c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('call_attendees_adopted', ?)",
              (datetime.datetime.now().isoformat(timespec="seconds"),))
    c.commit()


# ---------------- action items (v13) ----------------
ACTION_PRIORITIES = ["High", "Normal", "Low"]

def _adopt_action_owners(c):
    """One-time: match typed-in action owners to the roster where they line up."""
    if c.execute("SELECT value FROM meta WHERE key='action_owners_adopted'").fetchone():
        return
    people = {r["name"].strip().rstrip(".").lower(): r["id"]
              for r in c.execute("SELECT id, name FROM people")}
    for r in c.execute("SELECT id, owner FROM actions WHERE COALESCE(owner,'')<>'' "
                       "AND owner_person_id IS NULL").fetchall():
        pid = people.get((r["owner"] or "").strip().rstrip(".").lower())
        if pid:
            c.execute("UPDATE actions SET owner_person_id=? WHERE id=?", (pid, r["id"]))
    c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('action_owners_adopted', ?)",
              (datetime.datetime.now().isoformat(timespec="seconds"),))
    c.commit()


# ---------------- workstream template undo (v17) ----------------
# Every mutating action snapshots the template first, so any change can be walked
# back. Undo is itself snapshotted, which makes it reversible too.
TEMPLATE_HISTORY_LIMIT = 40

def template_snapshot(c, template_id):
    import json
    t = c.execute("SELECT name, category, avl_id, notes, source_url, active "
                  "FROM workstream_templates WHERE id=?", (template_id,)).fetchone()
    if not t:
        return None
    items = c.execute("SELECT doc_category, workstream, obligation, description, sort_order "
                      "FROM workstream_template_items WHERE template_id=? ORDER BY sort_order, id",
                      (template_id,)).fetchall()
    return json.dumps({"template": dict(t), "items": [dict(i) for i in items]})

def record_revision(c, template_id, action, detail, actor):
    """Snapshot the pre-change state. Call before mutating."""
    snap = template_snapshot(c, template_id)
    if snap is None:
        return
    c.execute("INSERT INTO template_revisions(template_id, action, detail, snapshot, actor, ts) "
              "VALUES(?,?,?,?,?,?)",
              (template_id, action, detail, snap, actor,
               datetime.datetime.now().isoformat(timespec="seconds")))
    # Keep the stack bounded; the oldest entries are the least likely to be undone.
    c.execute("DELETE FROM template_revisions WHERE template_id=? AND id NOT IN "
              "(SELECT id FROM template_revisions WHERE template_id=? ORDER BY id DESC LIMIT ?)",
              (template_id, template_id, TEMPLATE_HISTORY_LIMIT))

def restore_revision(c, rev_id, actor):
    """Roll a template back to a stored snapshot. Returns (template_id, action) or None."""
    import json
    rev = c.execute("SELECT * FROM template_revisions WHERE id=?", (rev_id,)).fetchone()
    if not rev:
        return None
    tid = rev["template_id"]
    if not c.execute("SELECT 1 FROM workstream_templates WHERE id=?", (tid,)).fetchone():
        return None
    record_revision(c, tid, "undo", f"reverted '{rev['action']}' from {rev['ts'][:16]}", actor)
    data = json.loads(rev["snapshot"])
    t = data["template"]
    c.execute("UPDATE workstream_templates SET name=?, category=?, avl_id=?, notes=?, "
              "source_url=?, active=? WHERE id=?",
              (t["name"], t["category"], t["avl_id"], t["notes"], t.get("source_url", ""),
               t.get("active", 1), tid))
    c.execute("DELETE FROM workstream_template_items WHERE template_id=?", (tid,))
    for i in data["items"]:
        c.execute("INSERT INTO workstream_template_items(template_id, doc_category, workstream, "
                  "obligation, description, sort_order) VALUES(?,?,?,?,?,?)",
                  (tid, i["doc_category"], i["workstream"], i["obligation"],
                   i["description"], i["sort_order"]))
    return tid, rev["action"]


# ---------------- IE / DNV reports (v18) ----------------
# Deliberately separate from workstream_templates: an IE technology review is a
# document being written by a third party, not a dataroom checklist. Scoped to a
# product, since a review is commissioned once and shown to several financiers.
IE_SCHEMA = """
CREATE TABLE IF NOT EXISTS ie_templates(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
  reviewer TEXT DEFAULT 'DNV', category TEXT DEFAULT '',
  notes TEXT DEFAULT '', source_url TEXT DEFAULT '', active INTEGER DEFAULT 1,
  created_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ie_template_sections(
  id INTEGER PRIMARY KEY,
  template_id INTEGER NOT NULL REFERENCES ie_templates(id) ON DELETE CASCADE,
  code TEXT DEFAULT '', title TEXT NOT NULL, owner TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ie_template_items(
  id INTEGER PRIMARY KEY,
  section_id INTEGER NOT NULL REFERENCES ie_template_sections(id) ON DELETE CASCADE,
  item_id TEXT DEFAULT '', sub_section TEXT DEFAULT '', review_item TEXT NOT NULL,
  evidence TEXT DEFAULT '', suggested_owner TEXT DEFAULT '',
  priority TEXT DEFAULT 'Normal', source TEXT DEFAULT '', sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ie_reports(
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  template_id INTEGER REFERENCES ie_templates(id) ON DELETE SET NULL,
  name TEXT NOT NULL, reviewer TEXT DEFAULT 'DNV', status TEXT DEFAULT 'Planning',
  kickoff_date TEXT DEFAULT '', target_date TEXT DEFAULT '', notes TEXT DEFAULT '',
  shared_with TEXT DEFAULT '', active INTEGER DEFAULT 1,
  created_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ie_report_sections(
  id INTEGER PRIMARY KEY,
  report_id INTEGER NOT NULL REFERENCES ie_reports(id) ON DELETE CASCADE,
  code TEXT DEFAULT '', title TEXT NOT NULL, owner TEXT DEFAULT '',
  owner_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
  narrative TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ie_report_items(
  id INTEGER PRIMARY KEY,
  report_id INTEGER NOT NULL REFERENCES ie_reports(id) ON DELETE CASCADE,
  section_id INTEGER NOT NULL REFERENCES ie_report_sections(id) ON DELETE CASCADE,
  item_id TEXT DEFAULT '', sub_section TEXT DEFAULT '', review_item TEXT NOT NULL,
  evidence TEXT DEFAULT '', priority TEXT DEFAULT 'Normal', source TEXT DEFAULT '',
  status TEXT DEFAULT 'Not Started', owner TEXT DEFAULT '',
  owner_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
  due_date TEXT DEFAULT '', gap TEXT DEFAULT '', notes TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0, updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS ie_template_revisions(
  id INTEGER PRIMARY KEY,
  template_id INTEGER NOT NULL REFERENCES ie_templates(id) ON DELETE CASCADE,
  action TEXT NOT NULL, detail TEXT DEFAULT '', snapshot TEXT NOT NULL,
  actor TEXT, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_ie_sec ON ie_template_sections(template_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_ie_itm ON ie_template_items(section_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_ie_rsec ON ie_report_sections(report_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_ie_ritm ON ie_report_items(report_id, section_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_ie_trev ON ie_template_revisions(template_id, id DESC);
"""

IE_REVIEWERS = ["DNV", "Black & Veatch", "Leidos", "PVEL", "RETC", "Other"]
IE_PRIORITIES = ["Critical", "High", "Normal", "Low"]
IE_ITEM_STATUSES = ["Not Started", "In Progress", "Submitted", "Accepted", "Blocked", "N/A"]
IE_REPORT_STATUSES = ["Planning", "Data Request", "In Review", "Draft Issued", "Final", "On Hold"]
IE_SEED_TAG = "seed:dnv-g4ess-2026-08"

def _seed_ie(c):
    """Insert any shipped baseline template that is not already present.

    Checked per template rather than all-or-nothing, so a database that already
    has an earlier baseline still picks up newly shipped ones.
    """
    from .seed_ie import BASELINES
    now = datetime.datetime.now().isoformat(timespec="seconds")
    added = 0
    for base in BASELINES:
        if c.execute("SELECT 1 FROM ie_templates WHERE name=?", (base["name"],)).fetchone():
            continue
        c.execute("INSERT INTO ie_templates(name, reviewer, category, notes, source_url, "
                  "created_by, created_at) VALUES(?,?,?,?,?,?,?)",
                  (base["name"], base["reviewer"], base["category"], base["notes"],
                   base.get("source_url", ""), IE_SEED_TAG, now))
        tid = c.execute("SELECT id FROM ie_templates WHERE name=?", (base["name"],)).fetchone()["id"]
        for si, (code, title, owner, items) in enumerate(base["sections"]):
            c.execute("INSERT INTO ie_template_sections(template_id, code, title, owner, sort_order) "
                      "VALUES(?,?,?,?,?)", (tid, code, title, owner, si))
            sid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            for ii, it in enumerate(items):
                c.execute("INSERT INTO ie_template_items(section_id, item_id, sub_section, "
                          "review_item, evidence, suggested_owner, priority, source, sort_order) "
                          "VALUES(?,?,?,?,?,?,?,?,?)",
                          (sid, it["item_id"], it["sub_section"], it["review_item"], it["evidence"],
                           it["suggested_owner"], it["priority"], it["source"], ii))
        added += 1
    if added:
        c.commit()

def ie_snapshot(c, template_id):
    import json
    t = c.execute("SELECT name, reviewer, category, notes, source_url, active "
                  "FROM ie_templates WHERE id=?", (template_id,)).fetchone()
    if not t:
        return None
    secs = []
    for s in c.execute("SELECT * FROM ie_template_sections WHERE template_id=? "
                       "ORDER BY sort_order, id", (template_id,)):
        items = c.execute("SELECT item_id, sub_section, review_item, evidence, suggested_owner, "
                          "priority, source, sort_order FROM ie_template_items WHERE section_id=? "
                          "ORDER BY sort_order, id", (s["id"],)).fetchall()
        secs.append({"code": s["code"], "title": s["title"], "owner": s["owner"],
                     "sort_order": s["sort_order"], "items": [dict(i) for i in items]})
    return json.dumps({"template": dict(t), "sections": secs})

def ie_record_revision(c, template_id, action, detail, actor):
    snap = ie_snapshot(c, template_id)
    if snap is None:
        return
    c.execute("INSERT INTO ie_template_revisions(template_id, action, detail, snapshot, actor, ts) "
              "VALUES(?,?,?,?,?,?)", (template_id, action, detail, snap, actor,
                                      datetime.datetime.now().isoformat(timespec="seconds")))
    c.execute("DELETE FROM ie_template_revisions WHERE template_id=? AND id NOT IN "
              "(SELECT id FROM ie_template_revisions WHERE template_id=? ORDER BY id DESC LIMIT ?)",
              (template_id, template_id, TEMPLATE_HISTORY_LIMIT))

def ie_restore_revision(c, rev_id, actor):
    import json
    rev = c.execute("SELECT * FROM ie_template_revisions WHERE id=?", (rev_id,)).fetchone()
    if not rev:
        return None
    tid = rev["template_id"]
    if not c.execute("SELECT 1 FROM ie_templates WHERE id=?", (tid,)).fetchone():
        return None
    ie_record_revision(c, tid, "undo", f"reverted '{rev['action']}' from {rev['ts'][:16]}", actor)
    data = json.loads(rev["snapshot"])
    t = data["template"]
    c.execute("UPDATE ie_templates SET name=?, reviewer=?, category=?, notes=?, source_url=?, "
              "active=? WHERE id=?", (t["name"], t["reviewer"], t["category"], t["notes"],
                                      t.get("source_url", ""), t.get("active", 1), tid))
    c.execute("DELETE FROM ie_template_sections WHERE template_id=?", (tid,))
    for s in data["sections"]:
        c.execute("INSERT INTO ie_template_sections(template_id, code, title, owner, sort_order) "
                  "VALUES(?,?,?,?,?)", (tid, s["code"], s["title"], s["owner"], s["sort_order"]))
        sid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        for i in s["items"]:
            c.execute("INSERT INTO ie_template_items(section_id, item_id, sub_section, review_item, "
                      "evidence, suggested_owner, priority, source, sort_order) "
                      "VALUES(?,?,?,?,?,?,?,?,?)",
                      (sid, i["item_id"], i["sub_section"], i["review_item"], i["evidence"],
                       i["suggested_owner"], i["priority"], i["source"], i["sort_order"]))
    return tid, rev["action"]


# ---------------- dataroom <-> IE link (v26) ----------------
# Requirement text that usually means "the IE report itself", used only to point
# the link control at the likely row - never to link anything automatically.
IE_REQUIREMENT_HINTS = ("dnv", "bankability", "technology review", "independent engineer",
                        " ie ", "ie /", "ie report", "b&v", "leidos", "tdd",
                        "technical due diligence")

def looks_like_ie_requirement(text):
    t = f" {(text or '').lower()} "
    return any(h in t for h in IE_REQUIREMENT_HINTS)

def ie_report_progress(c, report_ids):
    """{report_id: {...}} for reports linked from a dataroom checklist."""
    out = {}
    ids = [i for i in set(report_ids or []) if i]
    if not ids:
        return out
    qs = ",".join("?" * len(ids))
    for r in c.execute(
            f"SELECT r.id, r.name, r.reviewer, r.status, r.target_date, "
            "(SELECT COUNT(*) FROM ie_report_items i WHERE i.report_id=r.id) n, "
            "(SELECT COUNT(*) FROM ie_report_items i WHERE i.report_id=r.id "
            " AND i.status IN ('Accepted','N/A')) done "
            f"FROM ie_reports r WHERE r.id IN ({qs})", ids):
        out[r["id"]] = {"id": r["id"], "name": r["name"], "reviewer": r["reviewer"],
                        "status": r["status"], "target_date": r["target_date"],
                        "n": r["n"], "done": r["done"],
                        "pct": round(100 * r["done"] / r["n"]) if r["n"] else 0}
    return out


# ---------------- automatic backups (v30) ----------------
# Snapshots live beside the database, so on a hosted box they land on the same
# persistent disk. That protects against someone deleting the wrong thing; it
# does NOT protect against losing the disk. For that, pull one off the box - see
# the token endpoint in main.py.
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)) or ".", "backups")
AUTO_BACKUP_HOURS = float(os.environ.get("AUTO_BACKUP_HOURS", "24") or 0)
AUTO_BACKUP_KEEP = int(os.environ.get("AUTO_BACKUP_KEEP", "14") or 14)

def snapshot(dest=None):
    """A consistent copy, safe to take while the app is running.

    Uses SQLite's backup API rather than copying the file: in WAL mode recent
    commits live in the -wal sidecar and a plain copy would silently omit them.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = dest or os.path.join(
        BACKUP_DIR, "avl_%s.db" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    return dest

def list_snapshots():
    if not os.path.isdir(BACKUP_DIR):
        return []
    out = []
    for n in os.listdir(BACKUP_DIR):
        if n.startswith("avl_") and n.endswith(".db"):
            p = os.path.join(BACKUP_DIR, n)
            out.append({"name": n, "path": p, "bytes": os.path.getsize(p),
                        "mtime": os.path.getmtime(p)})
    return sorted(out, key=lambda r: r["mtime"], reverse=True)

def prune_snapshots(keep=None):
    keep = AUTO_BACKUP_KEEP if keep is None else keep
    for old in list_snapshots()[keep:]:
        try:
            os.remove(old["path"])
        except OSError:
            pass

def auto_backup():
    """Take one if the newest is older than the interval. Cheap to call often.

    Driven by activity rather than a scheduler, because a single web service has
    nowhere to run cron: a Render disk mounts to one service only, so a separate
    cron job cannot see this database.
    """
    if AUTO_BACKUP_HOURS <= 0:
        return None
    newest = list_snapshots()
    if newest and (datetime.datetime.now().timestamp() - newest[0]["mtime"]) < AUTO_BACKUP_HOURS * 3600:
        return None
    try:
        path = snapshot()
    except Exception:
        return None            # a backup failing must never block a login
    prune_snapshots()
    return path


# ---------------- dated commitments (v31) ----------------
# "We will submit the Gen4 dataroom to EnFin by 30 Nov" is not a task and not a
# listing status: it is a promise the pursuit carries, and several can be in
# flight at once (an IE draft, then the dataroom, then a revision). Actions hang
# off it rather than being it.
COMMITMENT_KINDS = ["Dataroom submission", "Package revision", "IE draft to reviewer",
                    "IE report final", "TPO response due", "Other"]
COMMITMENT_STATUSES = ["Planned", "Met", "Missed", "Cancelled"]
AT_RISK_DAYS = 14        # inside this window, outstanding required work is called out

def commitment_state(row, today=None):
    """Facts about where a commitment stands. No invented score - just the shape
    of it: days remaining, and whether it has already slipped."""
    today = today or datetime.date.today().isoformat()
    st = row["status"]
    if st != "Planned":
        return {"state": st.lower(), "days": None}
    try:
        d = (datetime.date.fromisoformat(row["due_date"]) - datetime.date.fromisoformat(today)).days
    except (ValueError, TypeError):
        return {"state": "planned", "days": None}
    if d < 0:
        return {"state": "overdue", "days": d}
    if d <= AT_RISK_DAYS:
        return {"state": "due-soon", "days": d}
    return {"state": "planned", "days": d}
