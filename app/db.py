"""SQLite data layer for the Qcells AVL Manager."""
import sqlite3, os, datetime

DB_PATH = os.environ.get("AVL_DB", os.path.join(os.path.dirname(__file__), "..", "avl.db"))

STATUSES = ["Listed", "In Review", "Execution", "Engagement", "Opportunity",
            "No Interest", "No Info", "N/A", "Pre-launch"]

ROLES = ["Account Manager (Sales)", "Sr. Commercial Rep (Sales)", "Product/Technical Rep (CE)"]

# Which side of the house someone sits on; drives who appears in each role picker.
ORGS = ["Sales", "Products / CE", "Other"]

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
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
    tt = [r[1] for r in c.execute("PRAGMA table_info(workstream_templates)")]
    if tt and "source_url" not in tt:
        c.execute("ALTER TABLE workstream_templates ADD COLUMN source_url TEXT DEFAULT ''")
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
    c.close()

def log(user_email, action, detail=""):
    c = conn()
    c.execute("INSERT INTO audit(ts, user_email, action, detail) VALUES(?,?,?,?)",
              (datetime.datetime.now().isoformat(timespec="seconds"), user_email, action, detail))
    c.commit(); c.close()


WORKSTREAMS = ["DNV / Bankability (IE)", "Certification & Standards", "3rd Party Validation (RETC/PVEL)",
               "Beta & Field Validation", "Factory Quality & Audit", "Design Tools / Software",
               "API + Cybersecurity", "BOM Change Control & Re-qual",
               "Tax Credit & Trade Compliance", "Commercial & Warranty Terms", "Corporate & Vendor Diligence"]
CHECK_STATUSES = ["Not Started", "In Progress", "Blocked", "Complete", "TBD"]


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
