"""SQLite data layer for the Qcells AVL Manager."""
import sqlite3, os, datetime

DB_PATH = os.environ.get("AVL_DB", os.path.join(os.path.dirname(__file__), "..", "avl.db"))

STATUSES = ["Listed", "In Review", "Execution", "Engagement", "Opportunity",
            "No Interest", "No Info", "N/A", "Pre-launch"]

ROLES = ["Account Manager (Sales)", "Sr. Commercial Rep (Sales)", "Product/Technical Rep (CE)"]

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
    _migrate(c)
    _seed_team(c)
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
