import os, datetime
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import db
from .auth import (AUTH_MODE, domain_ok, current_user, require_user, require_editor,
                   require_admin, get_role, ALLOWED_DOMAIN)

app = FastAPI(title="Qcells AVL Manager")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "change-me-in-prod"))
BASE = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

db.init_db()

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")

# ---------------- auth routes ----------------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None, "mode": AUTH_MODE, "domain": ALLOWED_DOMAIN})

@app.post("/login/dev")
def login_dev(request: Request, name: str = Form(...), email: str = Form(...)):
    if AUTH_MODE != "dev" or not domain_ok(email):
        return RedirectResponse("/login?error=domain", status_code=303)
    request.session["user"] = {"email": email.lower().strip(), "name": name.strip()}
    _touch_user(request.session["user"])
    return RedirectResponse("/", status_code=303)

@app.get("/login/sso")
async def login_sso(request: Request):
    from .auth import oauth_client
    redirect_uri = request.url_for("auth_callback")
    return await oauth_client().authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    from .auth import oauth_client
    token = await oauth_client().authorize_access_token(request)
    info = token.get("userinfo") or {}
    email = (info.get("email") or info.get("preferred_username") or "").lower()
    if not domain_ok(email):
        return RedirectResponse("/login?error=domain", status_code=303)
    request.session["user"] = {"email": email, "name": info.get("name", email.split("@")[0])}
    _touch_user(request.session["user"])
    return RedirectResponse("/", status_code=303)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

def _touch_user(user):
    c = db.conn()
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        c.execute("INSERT INTO users(email, name, role, last_login) VALUES(?,?, 'admin', ?)",
                  (user["email"], user["name"], now()))
        c.commit(); c.close(); return
    c.execute("INSERT INTO users(email, name, last_login) VALUES(?,?,?) "
              "ON CONFLICT(email) DO UPDATE SET name=excluded.name, last_login=excluded.last_login",
              (user["email"], user["name"], now()))
    c.commit(); c.close()

# ---------------- dashboard ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, show_eol: int = 0, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT * FROM avls WHERE active=1 ORDER BY id").fetchall()
    q = "SELECT * FROM products WHERE active=1 "
    if not show_eol:
        q += "AND lifecycle != 'EOL' "
    products = c.execute(q + "ORDER BY category, id").fetchall()
    grid = {}
    for row in c.execute("SELECT product_id, avl_id, status, note, updated_by, updated_at FROM listings"):
        grid[(row["product_id"], row["avl_id"])] = row
    am_map = {}
    for row in c.execute("SELECT a.avl_id, p.name FROM assignments a JOIN people p ON p.id=a.person_id "
                         "WHERE a.role LIKE 'Account Manager%' AND a.ended_at IS NULL AND a.avl_id IS NOT NULL"):
        am_map.setdefault(row["avl_id"], []).append(row["name"])
    avls = [dict(a) | {"account_manager": ", ".join(am_map.get(a["id"], [])) or a["account_manager"]} for a in avls]
    avls = [type("A", (), a) for a in avls]
    c.close()
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "avls": avls, "products": products,
        "grid": grid, "statuses": db.STATUSES, "show_eol": show_eol})

@app.post("/listing")
def update_listing(request: Request, product_id: int = Form(...), avl_id: int = Form(...),
                   status: str = Form(...), user=Depends(require_editor)):
    if status not in db.STATUSES:
        return RedirectResponse("/", status_code=303)
    c = db.conn()
    prev = c.execute("SELECT status FROM listings WHERE product_id=? AND avl_id=?",
                     (product_id, avl_id)).fetchone()
    old_status = prev["status"] if prev else None
    c.execute("INSERT INTO listings(product_id, avl_id, status, updated_by, updated_at) VALUES(?,?,?,?,?) "
              "ON CONFLICT(product_id, avl_id) DO UPDATE SET status=excluded.status, "
              "updated_by=excluded.updated_by, updated_at=excluded.updated_at",
              (product_id, avl_id, status, user["email"], now()))
    if old_status != status:
        c.execute("INSERT INTO status_history(product_id, avl_id, old_status, new_status, changed_by, ts) "
                  "VALUES(?,?,?,?,?,?)", (product_id, avl_id, old_status, status, user["email"], now()))
    pname = c.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()["name"]
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl_id,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "status", f"{pname} @ {aname} -> {status}")
    return RedirectResponse("/", status_code=303)

# ---------------- manage products / AVLs / managers ----------------
@app.get("/manage", response_class=HTMLResponse)
def manage(request: Request, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT * FROM avls ORDER BY active DESC, id").fetchall()
    products = c.execute("SELECT * FROM products ORDER BY active DESC, category, id").fetchall()
    c.close()
    return templates.TemplateResponse(request, "manage.html", {"user": user,
                                                      "avls": avls, "products": products})

@app.post("/products/add")
def add_product(request: Request, name: str = Form(...), category: str = Form(...),
                tech_reps: str = Form(""), launch_status: str = Form("Released"),
                lifecycle: str = Form("Active"), user=Depends(require_editor)):
    if lifecycle not in ("Roadmap", "Active", "EOL"):
        lifecycle = "Active"
    c = db.conn()
    c.execute("INSERT OR IGNORE INTO products(name, category, tech_reps, launch_status, lifecycle) "
              "VALUES(?,?,?,?,?)",
              (name.strip(), category, tech_reps.strip(), launch_status.strip(), lifecycle))
    c.commit(); c.close()
    db.log(user["email"], "product:add", name)
    return RedirectResponse("/manage", status_code=303)

@app.post("/products/{pid}/toggle")
def toggle_product(pid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE products SET active = 1 - active WHERE id=?", (pid,))
    name = c.execute("SELECT name, active FROM products WHERE id=?", (pid,)).fetchone()
    c.commit(); c.close()
    db.log(user["email"], "product:toggle", f"{name['name']} active={name['active']}")
    return RedirectResponse("/manage", status_code=303)

@app.post("/products/{pid}/reps")
def set_reps(pid: int, request: Request, tech_reps: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE products SET tech_reps=? WHERE id=?", (tech_reps.strip(), pid))
    name = c.execute("SELECT name FROM products WHERE id=?", (pid,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "product:reps", f"{name} -> {tech_reps}")
    return RedirectResponse("/manage", status_code=303)

@app.post("/avls/add")
def add_avl(request: Request, name: str = Form(...), account_manager: str = Form(""),
            sr_commercial_rep: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("INSERT OR IGNORE INTO avls(name, account_manager, sr_commercial_rep) VALUES(?,?,?)",
              (name.strip(), account_manager.strip(), sr_commercial_rep.strip()))
    c.commit(); c.close()
    db.log(user["email"], "avl:add", name)
    return RedirectResponse("/manage", status_code=303)

@app.post("/avls/{aid}/toggle")
def toggle_avl(aid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE avls SET active = 1 - active WHERE id=?", (aid,))
    row = c.execute("SELECT name, active FROM avls WHERE id=?", (aid,)).fetchone()
    c.commit(); c.close()
    db.log(user["email"], "avl:toggle", f"{row['name']} active={row['active']}")
    return RedirectResponse("/manage", status_code=303)

@app.post("/avls/{aid}/managers")
def set_managers(aid: int, request: Request, account_manager: str = Form(""),
                 sr_commercial_rep: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE avls SET account_manager=?, sr_commercial_rep=? WHERE id=?",
              (account_manager.strip(), sr_commercial_rep.strip(), aid))
    name = c.execute("SELECT name FROM avls WHERE id=?", (aid,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "avl:managers", f"{name} AM={account_manager} SCR={sr_commercial_rep}")
    return RedirectResponse("/manage", status_code=303)

# ---------------- audit ----------------
@app.get("/audit", response_class=HTMLResponse)
def audit(request: Request, user=Depends(require_user)):
    c = db.conn()
    rows = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 300").fetchall()
    c.close()
    return templates.TemplateResponse(request, "audit.html", {"user": user, "rows": rows})


# ---------------- interaction log ----------------
@app.get("/calls", response_class=HTMLResponse)
def calls(request: Request, avl: int = 0, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT * FROM avls WHERE active=1 ORDER BY name").fetchall()
    q = ("SELECT calls.*, avls.name AS avl_name FROM calls JOIN avls ON avls.id=calls.avl_id ")
    rows = (c.execute(q + "WHERE avl_id=? ORDER BY call_date DESC, calls.id DESC", (avl,)).fetchall()
            if avl else c.execute(q + "ORDER BY call_date DESC, calls.id DESC LIMIT 200").fetchall())
    c.close()
    return templates.TemplateResponse(request, "calls.html", {"user": user, "avls": avls,
                                                              "rows": rows, "sel": avl})

@app.post("/calls/add")
def add_call(request: Request, avl_id: int = Form(...), call_date: str = Form(...),
             call_type: str = Form("Joint"), qcells_attendees: str = Form(""),
             tpo_attendees: str = Form(""), topics: str = Form(""), outcomes: str = Form(""),
             owner_due: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("INSERT INTO calls(avl_id, call_date, call_type, qcells_attendees, tpo_attendees, "
              "topics, outcomes, owner_due, created_by, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (avl_id, call_date, call_type, qcells_attendees.strip(), tpo_attendees.strip(),
               topics.strip(), outcomes.strip(), owner_due.strip(), user["email"], now()))
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl_id,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "call:add", f"{aname} {call_date} ({call_type})")
    return RedirectResponse(f"/calls?avl={avl_id}", status_code=303)

# ---------------- history / changelog ----------------
@app.get("/history", response_class=HTMLResponse)
def history(request: Request, month: str = "", avl: int = 0, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT * FROM avls ORDER BY name").fetchall()
    q = ("SELECT h.*, p.name AS product, a.name AS avl_name FROM status_history h "
         "JOIN products p ON p.id=h.product_id JOIN avls a ON a.id=h.avl_id WHERE 1=1 ")
    args = []
    if month:
        q += "AND substr(h.ts,1,7)=? "; args.append(month)
    if avl:
        q += "AND h.avl_id=? "; args.append(avl)
    rows = c.execute(q + "ORDER BY h.ts DESC LIMIT 500", args).fetchall()
    months = [r[0] for r in c.execute("SELECT DISTINCT substr(ts,1,7) FROM status_history ORDER BY 1 DESC")]
    c.close()
    return templates.TemplateResponse(request, "history.html", {"user": user, "rows": rows,
        "avls": avls, "months": months, "sel_month": month, "sel_avl": avl})

# ---------------- executive dashboard ----------------
@app.get("/exec", response_class=HTMLResponse)
def exec_dash(request: Request, month: str = "", user=Depends(require_user)):
    c = db.conn()
    month = month or datetime.date.today().strftime("%Y-%m")
    changes = c.execute(
        "SELECT h.*, p.name AS product, a.name AS avl_name FROM status_history h "
        "JOIN products p ON p.id=h.product_id JOIN avls a ON a.id=h.avl_id "
        "WHERE substr(h.ts,1,7)=? ORDER BY h.ts", (month,)).fetchall()
    wins = [r for r in changes if r["new_status"] == "Listed"]
    risks = [r for r in changes if r["new_status"] in ("No Interest", "N/A")]
    calls_month = c.execute(
        "SELECT a.name AS avl_name, COUNT(*) AS n FROM calls JOIN avls a ON a.id=calls.avl_id "
        "WHERE substr(call_date,1,7)=? GROUP BY a.name ORDER BY n DESC", (month,)).fetchall()
    n_calls = sum(r["n"] for r in calls_month)
    counts = c.execute(
        "SELECT l.status, COUNT(*) AS n FROM listings l "
        "JOIN products p ON p.id=l.product_id AND p.active=1 "
        "JOIN avls a ON a.id=l.avl_id AND a.active=1 GROUP BY l.status ORDER BY n DESC").fetchall()
    listed_by_avl = c.execute(
        "SELECT a.name, SUM(CASE WHEN l.status='Listed' THEN 1 ELSE 0 END) AS listed, COUNT(*) AS total "
        "FROM listings l JOIN products p ON p.id=l.product_id AND p.active=1 "
        "JOIN avls a ON a.id=l.avl_id AND a.active=1 GROUP BY a.name ORDER BY listed DESC").fetchall()
    months = [r[0] for r in c.execute(
        "SELECT DISTINCT substr(ts,1,7) FROM status_history "
        "UNION SELECT DISTINCT substr(call_date,1,7) FROM calls ORDER BY 1 DESC")]
    c.close()
    return templates.TemplateResponse(request, "exec.html", {"user": user, "month": month,
        "months": months, "changes": changes, "wins": wins, "risks": risks,
        "calls_month": calls_month, "n_calls": n_calls, "counts": counts,
        "listed_by_avl": listed_by_avl})


@app.post("/products/{pid}/lifecycle")
def set_lifecycle(pid: int, request: Request, lifecycle: str = Form(...),
                  launch_status: str = Form(""), user=Depends(require_editor)):
    if lifecycle not in ("Roadmap", "Active", "EOL"):
        return RedirectResponse("/manage", status_code=303)
    c = db.conn()
    c.execute("UPDATE products SET lifecycle=?, launch_status=? WHERE id=?",
              (lifecycle, launch_status.strip(), pid))
    name = c.execute("SELECT name FROM products WHERE id=?", (pid,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "product:lifecycle", f"{name} -> {lifecycle} ({launch_status})")
    return RedirectResponse("/manage", status_code=303)


# ---------------- team: people + trifecta assignments ----------------
@app.get("/team", response_class=HTMLResponse)
def team(request: Request, user=Depends(require_user)):
    c = db.conn()
    people = c.execute("SELECT * FROM people WHERE active=1 ORDER BY name").fetchall()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    products = c.execute("SELECT id, name FROM products WHERE active=1 ORDER BY category, name").fetchall()
    current = c.execute(
        "SELECT a.id, p.name AS person, a.role, av.name AS avl_name, pr.name AS product_name, a.started_at "
        "FROM assignments a JOIN people p ON p.id=a.person_id "
        "LEFT JOIN avls av ON av.id=a.avl_id LEFT JOIN products pr ON pr.id=a.product_id "
        "WHERE a.ended_at IS NULL ORDER BY av.name, pr.name, a.role").fetchall()
    past = c.execute(
        "SELECT p.name AS person, a.role, av.name AS avl_name, pr.name AS product_name, a.started_at, a.ended_at "
        "FROM assignments a JOIN people p ON p.id=a.person_id "
        "LEFT JOIN avls av ON av.id=a.avl_id LEFT JOIN products pr ON pr.id=a.product_id "
        "WHERE a.ended_at IS NOT NULL ORDER BY a.ended_at DESC LIMIT 50").fetchall()
    # coverage: per AVL, who fills each role
    cov = {}
    for r in current:
        if r["avl_name"]:
            cov.setdefault(r["avl_name"], {}).setdefault(r["role"], []).append(r["person"])
    c.close()
    return templates.TemplateResponse(request, "team.html", {"user": user, "people": people,
        "avls": avls, "products": products, "current": current, "past": past,
        "cov": cov, "roles": db.ROLES})

@app.post("/team/person/add")
def add_person(request: Request, name: str = Form(...), email: str = Form(""),
               org: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("INSERT OR IGNORE INTO people(name, email, org) VALUES(?,?,?)",
              (name.strip(), email.strip(), org.strip()))
    c.commit(); c.close()
    db.log(user["email"], "person:add", name)
    return RedirectResponse("/team", status_code=303)

@app.post("/team/assign")
def assign(request: Request, person_id: int = Form(...), role: str = Form(...),
           avl_id: str = Form(""), product_id: str = Form(""), user=Depends(require_editor)):
    aid = int(avl_id) if avl_id else None
    pid = int(product_id) if product_id else None
    if role not in db.ROLES or (aid is None and pid is None):
        return RedirectResponse("/team", status_code=303)
    c = db.conn()
    c.execute("INSERT INTO assignments(person_id, role, avl_id, product_id, started_at, added_by) "
              "VALUES(?,?,?,?,?,?)", (person_id, role, aid, pid, now(), user["email"]))
    pname = c.execute("SELECT name FROM people WHERE id=?", (person_id,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "assign:add", f"{pname} as {role} (avl={aid}, product={pid})")
    return RedirectResponse("/team", status_code=303)

@app.post("/team/assign/{assign_id}/end")
def end_assignment(assign_id: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE assignments SET ended_at=? WHERE id=? AND ended_at IS NULL", (now(), assign_id))
    c.commit(); c.close()
    db.log(user["email"], "assign:end", f"assignment {assign_id}")
    return RedirectResponse("/team", status_code=303)
# ---- v6 features: appended to main.py ----
import io, csv, shutil, re as _re
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse

UPLOAD_DIR = os.path.join(os.path.dirname(BASE), "data_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _csv_response(rows, header, fname):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})

# ---------------- 1) per-cell notes ----------------
@app.post("/listing/note")
def listing_note(request: Request, product_id: int = Form(...), avl_id: int = Form(...),
                 note: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("INSERT INTO listings(product_id, avl_id, status, note, updated_by, updated_at) "
              "VALUES(?,?, 'No Info', ?, ?, ?) "
              "ON CONFLICT(product_id, avl_id) DO UPDATE SET note=excluded.note, "
              "updated_by=excluded.updated_by, updated_at=excluded.updated_at",
              (product_id, avl_id, note.strip(), user["email"], now()))
    c.commit(); c.close()
    db.log(user["email"], "note", f"p{product_id}/a{avl_id}: {note[:80]}")
    return RedirectResponse("/", status_code=303)

# ---------------- 2) CSV exports ----------------
@app.get("/export/matrix.csv")
def export_matrix(request: Request, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT * FROM avls WHERE active=1 ORDER BY id").fetchall()
    products = c.execute("SELECT * FROM products WHERE active=1 ORDER BY category, id").fetchall()
    grid = {(r["product_id"], r["avl_id"]): r for r in c.execute("SELECT * FROM listings")}
    rows = []
    for p in products:
        row = [p["category"], p["name"], p["lifecycle"], p["launch_status"]]
        for a in avls:
            cell = grid.get((p["id"], a["id"]))
            row.append(cell["status"] if cell else "")
        rows.append(row)
    c.close()
    return _csv_response(rows, ["Category", "Product", "Lifecycle", "Launch"] + [a["name"] for a in avls],
                         "avl_matrix.csv")

@app.get("/export/history.csv")
def export_history(request: Request, user=Depends(require_user)):
    c = db.conn()
    rows = [(r["ts"], r["avl_name"], r["product"], r["old_status"] or "", r["new_status"], r["changed_by"])
            for r in c.execute("SELECT h.ts, h.old_status, h.new_status, h.changed_by, "
                               "p.name AS product, a.name AS avl_name FROM status_history h "
                               "JOIN products p ON p.id=h.product_id JOIN avls a ON a.id=h.avl_id "
                               "ORDER BY h.ts DESC")]
    c.close()
    return _csv_response(rows, ["When", "TPO AVL", "Product", "From", "To", "Changed by"], "avl_history.csv")

@app.get("/export/calls.csv")
def export_calls(request: Request, user=Depends(require_user)):
    c = db.conn()
    rows = [(r["call_date"], r["avl_name"], r["call_type"], r["qcells_attendees"], r["tpo_attendees"],
             r["topics"], r["outcomes"], r["owner_due"], r["created_by"])
            for r in c.execute("SELECT calls.*, a.name AS avl_name FROM calls "
                               "JOIN avls a ON a.id=calls.avl_id ORDER BY call_date DESC")]
    c.close()
    return _csv_response(rows, ["Date", "TPO", "Type", "Qcells attendees", "TPO attendees",
                                "Topics", "Outcomes", "Owner/Due", "Logged by"], "avl_calls.csv")

# ---------------- 3) action items ----------------
@app.get("/actions", response_class=HTMLResponse)
def actions(request: Request, show: str = "open", user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    q = ("SELECT actions.*, a.name AS avl_name FROM actions LEFT JOIN avls a ON a.id=actions.avl_id ")
    q += "" if show == "all" else "WHERE actions.status='Open' "
    rows = c.execute(q + "ORDER BY CASE WHEN due_date='' THEN 1 ELSE 0 END, due_date").fetchall()
    today = datetime.date.today().isoformat()
    c.close()
    return templates.TemplateResponse(request, "actions.html", {"user": user, "rows": rows,
                                                                "avls": avls, "show": show, "today": today})

@app.post("/actions/add")
def add_action(request: Request, description: str = Form(...), avl_id: str = Form(""),
               owner: str = Form(""), due_date: str = Form(""), call_id: str = Form(""),
               user=Depends(require_editor)):
    c = db.conn()
    c.execute("INSERT INTO actions(avl_id, call_id, description, owner, due_date, created_by, created_at) "
              "VALUES(?,?,?,?,?,?,?)",
              (int(avl_id) if avl_id else None, int(call_id) if call_id else None,
               description.strip(), owner.strip(), due_date, user["email"], now()))
    c.commit(); c.close()
    db.log(user["email"], "action:add", description[:80])
    return RedirectResponse("/actions", status_code=303)

@app.post("/actions/{aid}/done")
def action_done(aid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE actions SET status='Done', closed_at=? WHERE id=?", (now(), aid))
    c.commit(); c.close()
    db.log(user["email"], "action:done", str(aid))
    return RedirectResponse("/actions", status_code=303)

# ---------------- 4) PPTX exports ----------------
def _pptx_status_deck():
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    FILLS = {"Listed": (0xC6,0xEF,0xCE), "In Review": (0xBD,0xD7,0xEE), "Execution": (0xA8,0xF0,0xEA),
             "Engagement": (0xFC,0xD9,0xC4), "Opportunity": (0xFC,0xE4,0xD6), "No Interest": (0xF8,0xCB,0xAD),
             "No Info": (0xFF,0xF2,0xCC), "N/A": (0xFF,0xFF,0xFF), "Pre-launch": (0xED,0xED,0xED)}
    NAVY = RGBColor(0x1F,0x38,0x64)
    pres = Presentation(); pres.slide_width = Inches(13.333); pres.slide_height = Inches(7.5)
    s = pres.slides.add_slide(pres.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.4), Inches(0.15), Inches(12.5), Inches(0.5))
    r = tb.text_frame.paragraphs[0].add_run()
    r.text = f"AVL Status - Current products ({datetime.date.today().strftime('%b %Y')})"
    r.font.size = Pt(24); r.font.bold = True; r.font.color.rgb = NAVY
    c = db.conn()
    avls = c.execute("SELECT * FROM avls WHERE active=1 ORDER BY id").fetchall()
    products = c.execute("SELECT * FROM products WHERE active=1 AND lifecycle != 'EOL' "
                         "ORDER BY category, id").fetchall()
    grid = {(x["product_id"], x["avl_id"]): x["status"] for x in c.execute("SELECT * FROM listings")}
    c.close()
    nrows, ncols = len(products) + 1, len(avls) + 1
    gf = s.shapes.add_table(nrows, ncols, Inches(0.4), Inches(0.75),
                            Inches(12.5), Inches(min(6.2, 0.34 * nrows)))
    tbl = gf.table
    tbl.columns[0].width = Inches(2.9)
    for i in range(1, ncols):
        tbl.columns[i].width = Inches((12.5 - 2.9) / len(avls))
    def cell(rr, cc, text, bold=False, fill=None, size=9):
        cl = tbl.cell(rr, cc); cl.text = text
        for para in cl.text_frame.paragraphs:
            for run in para.runs:
                run.font.size = Pt(size); run.font.bold = bold
        if fill:
            cl.fill.solid(); cl.fill.fore_color.rgb = RGBColor(*fill)
    cell(0, 0, "Product", bold=True)
    for j, a in enumerate(avls, 1):
        cell(0, j, a["name"], bold=True, size=8)
    for i, p in enumerate(products, 1):
        label = p["name"] + (f" [{p['lifecycle']} {p['launch_status']}]" if p["lifecycle"] != "Active" else "")
        cell(i, 0, label, bold=True, size=8)
        for j, a in enumerate(avls, 1):
            st = grid.get((p["id"], a["id"]), "")
            cell(i, j, st, fill=FILLS.get(st), size=8)
    buf = io.BytesIO(); pres.save(buf); buf.seek(0)
    return buf

@app.get("/export/status.pptx")
def export_status_pptx(request: Request, user=Depends(require_user)):
    buf = _pptx_status_deck()
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=AVL_Status_Snapshot.pptx"})

# ---------------- 5) dataroom checklists ----------------
@app.get("/dataroom", response_class=HTMLResponse)
def dataroom(request: Request, product: int = 0, avl: int = 0, user=Depends(require_user)):
    c = db.conn()
    products = c.execute("SELECT id, name FROM products WHERE active=1 ORDER BY category, name").fetchall()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    product = product or (products[0]["id"] if products else 0)
    avl = avl or (avls[0]["id"] if avls else 0)
    items = c.execute("SELECT * FROM checklist_items WHERE product_id=? AND avl_id=? ORDER BY id",
                      (product, avl)).fetchall()
    c.close()
    return templates.TemplateResponse(request, "dataroom.html", {"user": user, "products": products,
        "avls": avls, "items": items, "sel_p": product, "sel_a": avl,
        "check_statuses": db.CHECK_STATUSES})

@app.post("/dataroom/seed")
def dataroom_seed(request: Request, product_id: int = Form(...), avl_id: int = Form(...),
                  user=Depends(require_editor)):
    c = db.conn()
    if not c.execute("SELECT COUNT(*) FROM checklist_items WHERE product_id=? AND avl_id=?",
                     (product_id, avl_id)).fetchone()[0]:
        for w in db.WORKSTREAMS:
            c.execute("INSERT INTO checklist_items(product_id, avl_id, workstream, updated_by, updated_at) "
                      "VALUES(?,?,?,?,?)", (product_id, avl_id, w, user["email"], now()))
        c.commit()
    c.close()
    db.log(user["email"], "dataroom:seed", f"p{product_id}/a{avl_id}")
    return RedirectResponse(f"/dataroom?product={product_id}&avl={avl_id}", status_code=303)

@app.post("/dataroom/{iid}")
def dataroom_update(iid: int, request: Request, status: str = Form(...), pct: str = Form(""),
                    eta: str = Form(""), owner: str = Form(""), notes: str = Form(""),
                    user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE checklist_items SET status=?, pct=?, eta=?, owner=?, notes=?, "
              "updated_by=?, updated_at=? WHERE id=?",
              (status, pct.strip(), eta.strip(), owner.strip(), notes.strip(),
               user["email"], now(), iid))
    row = c.execute("SELECT product_id, avl_id, workstream FROM checklist_items WHERE id=?", (iid,)).fetchone()
    c.commit(); c.close()
    db.log(user["email"], "dataroom:update", f"{row['workstream']} -> {status}")
    return RedirectResponse(f"/dataroom?product={row['product_id']}&avl={row['avl_id']}", status_code=303)

# ---------------- 6) weekly digest ----------------
def _digest_data(days=7):
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    c = db.conn()
    changes = c.execute("SELECT h.ts, h.old_status, h.new_status, p.name AS product, a.name AS avl_name "
                        "FROM status_history h JOIN products p ON p.id=h.product_id "
                        "JOIN avls a ON a.id=h.avl_id WHERE h.ts>=? ORDER BY h.ts DESC", (since,)).fetchall()
    calls = c.execute("SELECT calls.*, a.name AS avl_name FROM calls JOIN avls a ON a.id=calls.avl_id "
                      "WHERE call_date>=? ORDER BY call_date DESC", (since,)).fetchall()
    today = datetime.date.today().isoformat()
    overdue = c.execute("SELECT actions.*, a.name AS avl_name FROM actions "
                        "LEFT JOIN avls a ON a.id=actions.avl_id "
                        "WHERE status='Open' AND due_date != '' AND due_date < ? ORDER BY due_date",
                        (today,)).fetchall()
    c.close()
    return {"since": since, "changes": changes, "calls": calls, "overdue": overdue}

@app.get("/digest", response_class=HTMLResponse)
def digest_preview(request: Request, user=Depends(require_user)):
    d = _digest_data()
    return templates.TemplateResponse(request, "digest.html", {"user": user, **d})

# ---------------- 7-8) admin: roles + backup ----------------
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, user=Depends(require_admin)):
    c = db.conn()
    users = c.execute("SELECT * FROM users ORDER BY email").fetchall()
    c.close()
    return templates.TemplateResponse(request, "admin.html", {"user": user, "users": users,
                                                              "auth_mode": AUTH_MODE})

@app.post("/admin/role")
def set_role(request: Request, email: str = Form(...), role: str = Form(...),
             user=Depends(require_admin)):
    if role in ("viewer", "editor", "admin"):
        c = db.conn()
        c.execute("UPDATE users SET role=? WHERE email=?", (role, email))
        c.commit(); c.close()
        db.log(user["email"], "role", f"{email} -> {role}")
    return RedirectResponse("/admin", status_code=303)

@app.get("/admin/backup")
def backup(request: Request, user=Depends(require_admin)):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(UPLOAD_DIR, f"avl_backup_{stamp}.db")
    shutil.copy(db.DB_PATH, dest)
    db.log(user["email"], "backup", dest)
    return FileResponse(dest, filename=f"avl_backup_{stamp}.db")

# ---------------- 9) attachments ----------------
@app.get("/files", response_class=HTMLResponse)
def files(request: Request, user=Depends(require_user)):
    c = db.conn()
    products = c.execute("SELECT id, name FROM products ORDER BY name").fetchall()
    avls = c.execute("SELECT id, name FROM avls ORDER BY name").fetchall()
    calls_ = c.execute("SELECT calls.id, call_date, a.name AS avl_name FROM calls "
                       "JOIN avls a ON a.id=calls.avl_id ORDER BY call_date DESC LIMIT 100").fetchall()
    atts = c.execute("SELECT * FROM attachments ORDER BY id DESC").fetchall()
    names = {"product": {p["id"]: p["name"] for p in products},
             "avl": {a["id"]: a["name"] for a in avls},
             "call": {r["id"]: f"{r['avl_name']} {r['call_date']}" for r in calls_}}
    c.close()
    return templates.TemplateResponse(request, "files.html", {"user": user, "products": products,
        "avls": avls, "calls": calls_, "atts": atts, "names": names})

@app.post("/files/upload")
async def upload(request: Request, kind: str = Form(...), ref_id: int = Form(...),
                 f: UploadFile = File(...), user=Depends(require_editor)):
    if kind not in ("product", "avl", "call"):
        return RedirectResponse("/files", status_code=303)
    safe = _re.sub(r"[^A-Za-z0-9._-]", "_", f.filename or "file")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stored = os.path.join(UPLOAD_DIR, f"{stamp}_{safe}")
    with open(stored, "wb") as out:
        out.write(await f.read())
    c = db.conn()
    c.execute("INSERT INTO attachments(kind, ref_id, filename, stored_path, uploaded_by, uploaded_at) "
              "VALUES(?,?,?,?,?,?)", (kind, ref_id, safe, stored, user["email"], now()))
    c.commit(); c.close()
    db.log(user["email"], "file:upload", f"{kind}#{ref_id} {safe}")
    return RedirectResponse("/files", status_code=303)

@app.get("/files/{att_id}/download")
def download(att_id: int, request: Request, user=Depends(require_user)):
    c = db.conn()
    row = c.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    c.close()
    if not row:
        return RedirectResponse("/files", status_code=303)
    return FileResponse(row["stored_path"], filename=row["filename"])
