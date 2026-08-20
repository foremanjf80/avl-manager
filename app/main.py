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
    people = c.execute("SELECT id, name, org FROM people WHERE active=1 ORDER BY name").fetchall()
    AM, SCR, PT = db.ROLES
    # Who currently holds each seat, so the pickers come up pre-selected.
    holders = {
        "avl": {a["id"]: {"am": [r["person_id"] for r in db.role_holders(c, AM, avl_id=a["id"])],
                          "scr": [r["person_id"] for r in db.role_holders(c, SCR, avl_id=a["id"])]}
                for a in avls},
        "product": {p["id"]: [r["person_id"] for r in db.role_holders(c, PT, product_id=p["id"])]
                    for p in products},
    }
    AM_, SCR_, PT_ = db.ROLES
    # Options are built per row so somebody already holding a seat stays listed
    # even if their team would not normally be offered for it.
    prod_opts = {p["id"]: db.role_options(people, PT_, holders["product"].get(p["id"], []))
                 for p in products}
    avl_opts = {a["id"]: {
        "am": db.role_options(people, AM_, holders["avl"].get(a["id"], {}).get("am", [])),
        "scr": db.role_options(people, SCR_, holders["avl"].get(a["id"], {}).get("scr", [])),
    } for a in avls}
    new_prod_opts = db.role_options(people, PT_)
    new_avl_opts = db.role_options(people, AM_)
    c.close()
    return templates.TemplateResponse(request, "manage.html", {"user": user,
                            "avls": avls, "products": products, "categories": db.CATEGORIES,
                            "people": people, "holders": holders,
                            "prod_opts": prod_opts, "avl_opts": avl_opts,
                            "new_prod_opts": new_prod_opts, "new_avl_opts": new_avl_opts})

@app.post("/products/add")
def add_product(request: Request, name: str = Form(...), category: str = Form(...),
                person_ids: list[int] = Form(default=[]), launch_status: str = Form("Released"),
                lifecycle: str = Form("Active"), user=Depends(require_editor)):
    if lifecycle not in ("Roadmap", "Active", "EOL"):
        lifecycle = "Active"
    _, _, PT = db.ROLES
    c = db.conn()
    c.execute("INSERT OR IGNORE INTO products(name, category, launch_status, lifecycle) "
              "VALUES(?,?,?,?)", (name.strip(), category, launch_status.strip(), lifecycle))
    row = c.execute("SELECT id FROM products WHERE name=?", (name.strip(),)).fetchone()
    if row:
        db.set_role_holders(c, PT, person_ids, product_id=row["id"], actor=user["email"])
        db.refresh_rep_cache(c, product_id=row["id"])
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
def set_reps(pid: int, request: Request, person_ids: list[int] = Form(default=[]),
             user=Depends(require_editor)):
    """Product/Technical reps come from the Team roster, never free text."""
    _, _, PT = db.ROLES
    c = db.conn()
    added, removed = db.set_role_holders(c, PT, person_ids, product_id=pid, actor=user["email"])
    db.refresh_rep_cache(c, product_id=pid)
    name = c.execute("SELECT name FROM products WHERE id=?", (pid,)).fetchone()["name"]
    c.commit(); c.close()
    if added or removed:
        db.log(user["email"], "product:reps",
               f"{name}: +{', '.join(added) or '-'} / -{', '.join(removed) or '-'}")
    return RedirectResponse("/manage", status_code=303)

@app.post("/avls/add")
def add_avl(request: Request, name: str = Form(...), account_manager_id: str = Form(""),
            sr_commercial_rep_id: str = Form(""), user=Depends(require_editor)):
    AM, SCR, _ = db.ROLES
    c = db.conn()
    c.execute("INSERT OR IGNORE INTO avls(name) VALUES(?)", (name.strip(),))
    row = c.execute("SELECT id FROM avls WHERE name=?", (name.strip(),)).fetchone()
    if row:
        for role, raw in ((AM, account_manager_id), (SCR, sr_commercial_rep_id)):
            db.set_role_holders(c, role, [int(raw)] if raw.strip().isdigit() else [],
                                avl_id=row["id"], actor=user["email"])
        db.refresh_rep_cache(c, avl_id=row["id"])
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
def set_managers(aid: int, request: Request, account_manager_id: str = Form(""),
                 sr_commercial_rep_id: str = Form(""), user=Depends(require_editor)):
    """AM and Sr. Commercial Rep come from the Team roster; blank = seat vacant."""
    AM, SCR, _ = db.ROLES
    c = db.conn()
    changes = []
    for role, raw in ((AM, account_manager_id), (SCR, sr_commercial_rep_id)):
        picked = [int(raw)] if raw.strip().isdigit() else []
        added, removed = db.set_role_holders(c, role, picked, avl_id=aid, actor=user["email"])
        if added or removed:
            changes.append(f"{role.split(' (')[0]}: +{', '.join(added) or '-'} / -{', '.join(removed) or '-'}")
    db.refresh_rep_cache(c, avl_id=aid)
    name = c.execute("SELECT name FROM avls WHERE id=?", (aid,)).fetchone()["name"]
    c.commit(); c.close()
    if changes:
        db.log(user["email"], "avl:managers", f"{name} " + "; ".join(changes))
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
def calls(request: Request, avl: int = 0, q: str = "", edit: int = 0,
          user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT * FROM avls WHERE active=1 ORDER BY name").fetchall()
    people = c.execute("SELECT id, name, org FROM people WHERE active=1 ORDER BY name").fetchall()
    sql = "SELECT calls.*, avls.name AS avl_name FROM calls JOIN avls ON avls.id=calls.avl_id WHERE 1=1 "
    params = []
    if avl:
        sql += "AND avl_id=? "
        params.append(avl)
    if q.strip():
        sql += ("AND (topics LIKE ? OR outcomes LIKE ? OR owner_due LIKE ? "
                "OR qcells_attendees LIKE ? OR tpo_attendees LIKE ?) ")
        params += [f"%{q.strip()}%"] * 5
    rows = c.execute(sql + "ORDER BY call_date DESC, calls.id DESC LIMIT 300", params).fetchall()
    # What each logged call already has selected, so the edit form comes up filled in.
    picked = {r["id"]: {"qcells": [], "tpo": [], "other_q": [], "other_t": []} for r in rows}
    if rows:
        qs = ",".join("?" * len(rows))
        for at in c.execute(f"SELECT * FROM call_attendees WHERE call_id IN ({qs})",
                            [r["id"] for r in rows]):
            pk = picked[at["call_id"]]
            if at["person_id"]:
                pk["qcells"].append(at["person_id"])
            elif at["contact_id"]:
                pk["tpo"].append(at["contact_id"])
            else:
                pk["other_q" if at["side"] == "qcells" else "other_t"].append(at["name"])
    # avl -> its active contacts, driving the TPO attendee picker
    by_avl = {}
    for ct in c.execute("SELECT id, avl_id, name, role FROM contacts WHERE active=1 ORDER BY name"):
        by_avl.setdefault(str(ct["avl_id"]), []).append(
            {"id": ct["id"], "name": ct["name"], "role": ct["role"]})
    c.close()
    return templates.TemplateResponse(request, "calls.html", {"user": user, "avls": avls,
        "rows": rows, "sel": avl, "q": q, "people": people, "contacts_by_avl": by_avl,
        "picked": picked, "call_types": db.CALL_TYPES, "edit": edit,
        "today": datetime.date.today().isoformat()})

def _save_attendees(c, cid, qcells_person_ids, tpo_contact_ids, qcells_other, tpo_other):
    db.set_call_attendees(c, cid, "qcells", person_ids=qcells_person_ids, other=qcells_other)
    db.set_call_attendees(c, cid, "tpo", contact_ids=tpo_contact_ids, other=tpo_other)

@app.post("/calls/add")
def add_call(request: Request, avl_id: int = Form(...), call_date: str = Form(...),
             call_type: str = Form("Joint"),
             qcells_person_ids: list[int] = Form(default=[]),
             tpo_contact_ids: list[int] = Form(default=[]),
             qcells_other: str = Form(""), tpo_other: str = Form(""),
             topics: str = Form(""), outcomes: str = Form(""),
             owner_due: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("INSERT INTO calls(avl_id, call_date, call_type, topics, outcomes, owner_due, "
              "created_by, created_at) VALUES(?,?,?,?,?,?,?,?)",
              (avl_id, call_date, call_type, topics.strip(), outcomes.strip(),
               owner_due.strip(), user["email"], now()))
    cid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    _save_attendees(c, cid, qcells_person_ids, tpo_contact_ids, qcells_other, tpo_other)
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl_id,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "call:add", f"{aname} {call_date} ({call_type})")
    return RedirectResponse(f"/calls?avl={avl_id}", status_code=303)

@app.post("/calls/{cid}/save")
def save_call(cid: int, request: Request, avl_id: int = Form(...), call_date: str = Form(...),
              call_type: str = Form("Joint"),
              qcells_person_ids: list[int] = Form(default=[]),
              tpo_contact_ids: list[int] = Form(default=[]),
              qcells_other: str = Form(""), tpo_other: str = Form(""),
              topics: str = Form(""), outcomes: str = Form(""),
              owner_due: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    if not c.execute("SELECT 1 FROM calls WHERE id=?", (cid,)).fetchone():
        c.close()
        return RedirectResponse("/calls", status_code=303)
    c.execute("UPDATE calls SET avl_id=?, call_date=?, call_type=?, topics=?, outcomes=?, "
              "owner_due=? WHERE id=?", (avl_id, call_date, call_type, topics.strip(),
                                         outcomes.strip(), owner_due.strip(), cid))
    _save_attendees(c, cid, qcells_person_ids, tpo_contact_ids, qcells_other, tpo_other)
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl_id,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "call:save", f"{aname} {call_date}")
    return RedirectResponse(f"/calls?avl={avl_id}", status_code=303)

@app.post("/calls/{cid}/delete")
def delete_call(cid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT calls.*, a.name AS avl_name FROM calls JOIN avls a ON a.id=calls.avl_id "
                    "WHERE calls.id=?", (cid,)).fetchone()
    if row:
        c.execute("DELETE FROM call_attendees WHERE call_id=?", (cid,))
        c.execute("DELETE FROM calls WHERE id=?", (cid,))
        c.commit()
        db.log(user["email"], "call:delete", f"{row['avl_name']} {row['call_date']}")
    c.close()
    return RedirectResponse(f"/calls?avl={row['avl_id'] if row else 0}", status_code=303)

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
    people = c.execute("SELECT * FROM people ORDER BY active DESC, name").fetchall()
    active_people = [p for p in people if p["active"]]
    load = {r["person_id"]: r["n"] for r in c.execute(
        "SELECT person_id, COUNT(*) AS n FROM assignments WHERE ended_at IS NULL GROUP BY person_id")}
    orgs = db.orgs_in_use(c)
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
        "active_people": active_people, "load": load,
        "avls": avls, "products": products, "current": current, "past": past,
        "cov": cov, "roles": db.ROLES, "orgs": orgs})

def _org_value(org, org_other):
    """"Other" is a prompt to define the team, not a bucket to file people in."""
    o = (org or "").strip()
    return (org_other or "").strip() if o in ("", "Other") and org_other.strip() else o

@app.post("/team/person/add")
def add_person(request: Request, name: str = Form(...), email: str = Form(""),
               org: str = Form(""), org_other: str = Form(""), user=Depends(require_editor)):
    org = _org_value(org, org_other)
    nm = name.strip()
    if not nm:
        return RedirectResponse("/team", status_code=303)
    c = db.conn()
    row = c.execute("SELECT id, active FROM people WHERE lower(name)=lower(?)", (nm,)).fetchone()
    if row:
        # Re-adding someone who was retired brings them back rather than duplicating.
        c.execute("UPDATE people SET active=1, email=COALESCE(NULLIF(?,''), email), "
                  "org=COALESCE(NULLIF(?,''), org) WHERE id=?", (email.strip(), org.strip(), row["id"]))
        c.commit(); c.close()
        db.log(user["email"], "person:restore", nm)
        return RedirectResponse("/team", status_code=303)
    c.execute("INSERT INTO people(name, email, org) VALUES(?,?,?)",
              (nm, email.strip(), org.strip()))
    c.commit(); c.close()
    db.log(user["email"], "person:add", nm)
    return RedirectResponse("/team", status_code=303)

@app.post("/team/person/{person_id}/save")
def save_person(person_id: int, request: Request, name: str = Form(...), email: str = Form(""),
                org: str = Form(""), org_other: str = Form(""), user=Depends(require_editor)):
    org = _org_value(org, org_other)
    nm = name.strip()
    if not nm:
        return RedirectResponse("/team", status_code=303)
    c = db.conn()
    if c.execute("SELECT 1 FROM people WHERE lower(name)=lower(?) AND id<>?", (nm, person_id)).fetchone():
        c.close()
        return RedirectResponse("/team?err=dupname", status_code=303)
    c.execute("UPDATE people SET name=?, email=?, org=? WHERE id=?",
              (nm, email.strip(), org.strip(), person_id))
    db.refresh_all_rep_caches(c)
    c.commit(); c.close()
    db.log(user["email"], "person:save", nm)
    return RedirectResponse("/team", status_code=303)

@app.post("/team/person/{person_id}/toggle")
def toggle_person(person_id: int, request: Request, user=Depends(require_editor)):
    """Retiring someone ends their open assignments so they leave every picker."""
    c = db.conn()
    row = c.execute("SELECT name, active FROM people WHERE id=?", (person_id,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/team", status_code=303)
    going_inactive = bool(row["active"])
    c.execute("UPDATE people SET active = 1 - active WHERE id=?", (person_id,))
    ended = 0
    if going_inactive:
        open_rows = c.execute("SELECT id, avl_id, product_id FROM assignments "
                              "WHERE person_id=? AND ended_at IS NULL", (person_id,)).fetchall()
        for a in open_rows:
            c.execute("UPDATE assignments SET ended_at=? WHERE id=?", (now(), a["id"]))
            db.refresh_rep_cache(c, avl_id=a["avl_id"], product_id=a["product_id"])
        ended = len(open_rows)
    c.commit(); c.close()
    db.log(user["email"], "person:toggle",
           f"{row['name']} -> {'retired' if going_inactive else 'active'}"
           + (f" ({ended} assignment(s) ended)" if ended else ""))
    return RedirectResponse("/team", status_code=303)

@app.post("/team/assign")
def assign(request: Request, person_id: int = Form(...), role: str = Form(...),
           avl_id: str = Form(""), product_id: str = Form(""), user=Depends(require_editor)):
    aid = int(avl_id) if avl_id else None
    pid = int(product_id) if product_id else None
    if role not in db.ROLES or (aid is None and pid is None):
        return RedirectResponse("/team", status_code=303)
    c = db.conn()
    if not c.execute("SELECT 1 FROM people WHERE id=? AND active=1", (person_id,)).fetchone():
        c.close()
        return RedirectResponse("/team?err=inactive", status_code=303)
    c.execute("INSERT INTO assignments(person_id, role, avl_id, product_id, started_at, added_by) "
              "VALUES(?,?,?,?,?,?)", (person_id, role, aid, pid, now(), user["email"]))
    pname = c.execute("SELECT name FROM people WHERE id=?", (person_id,)).fetchone()["name"]
    db.refresh_rep_cache(c, avl_id=aid, product_id=pid)
    c.commit(); c.close()
    db.log(user["email"], "assign:add", f"{pname} as {role} (avl={aid}, product={pid})")
    return RedirectResponse("/team", status_code=303)

@app.post("/team/assign/{assign_id}/end")
def end_assignment(assign_id: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT avl_id, product_id FROM assignments WHERE id=?", (assign_id,)).fetchone()
    c.execute("UPDATE assignments SET ended_at=? WHERE id=? AND ended_at IS NULL", (now(), assign_id))
    if row:
        db.refresh_rep_cache(c, avl_id=row["avl_id"], product_id=row["product_id"])
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
def _requirement_picker(c, avl_id=None):
    """avl -> product -> [requirement] for the checklist-link dropdowns."""
    q = ("SELECT ci.id, ci.workstream, ci.doc_category, ci.status, ci.product_id, ci.avl_id, "
         "p.name AS product FROM checklist_items ci JOIN products p ON p.id=ci.product_id ")
    args = []
    if avl_id:
        q += "WHERE ci.avl_id=? "
        args.append(avl_id)
    tree = {}
    for r in c.execute(q + "ORDER BY p.name, ci.sort_order, ci.id", args):
        tree.setdefault(str(r["avl_id"]), {}).setdefault(
            str(r["product_id"]), {"name": r["product"], "items": []})["items"].append(
            {"id": r["id"], "ws": r["workstream"], "cat": r["doc_category"], "status": r["status"]})
    return tree

@app.get("/actions", response_class=HTMLResponse)
def actions(request: Request, show: str = "open", avl: int = 0, owner: int = 0,
            edit: int = 0, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    people = c.execute("SELECT id, name, org FROM people WHERE active=1 ORDER BY name").fetchall()
    q = ("SELECT actions.*, a.name AS avl_name, pe.name AS owner_name, "
         "pr.name AS product_name, ci.workstream, ci.doc_category, ci.status AS req_status "
         "FROM actions "
         "LEFT JOIN avls a ON a.id=actions.avl_id "
         "LEFT JOIN people pe ON pe.id=actions.owner_person_id "
         "LEFT JOIN checklist_items ci ON ci.id=actions.checklist_item_id "
         "LEFT JOIN products pr ON pr.id=actions.product_id WHERE 1=1 ")
    params = []
    if show != "all":
        q += "AND actions.status='Open' "
    if avl:
        q += "AND actions.avl_id=? "
        params.append(avl)
    if owner:
        q += "AND actions.owner_person_id=? "
        params.append(owner)
    rows = c.execute(q + "ORDER BY CASE WHEN COALESCE(due_date,'')='' THEN 1 ELSE 0 END, "
                     "due_date, actions.id DESC", params).fetchall()
    today = datetime.date.today().isoformat()
    n_overdue = sum(1 for r in rows if r["status"] == "Open" and r["due_date"] and r["due_date"] < today)
    tree = _requirement_picker(c)
    c.close()
    return templates.TemplateResponse(request, "actions.html", {"user": user, "rows": rows,
        "avls": avls, "people": people, "show": show, "today": today, "sel_a": avl,
        "sel_o": owner, "edit": edit, "tree": tree, "priorities": db.ACTION_PRIORITIES,
        "n_overdue": n_overdue})

def _action_fields(c, avl_id, product_id, checklist_item_id, owner_person_id):
    """A linked requirement is authoritative for the AVL and product it belongs to."""
    def as_id(v):
        # 0 is the "any / none" sentinel the filter selects use; never a real row.
        return int(v) if str(v).strip().isdigit() and int(v) > 0 else None
    aid, pid, cid = as_id(avl_id), as_id(product_id), as_id(checklist_item_id)
    if cid:
        row = c.execute("SELECT avl_id, product_id FROM checklist_items WHERE id=?", (cid,)).fetchone()
        if row:
            aid, pid = row["avl_id"], row["product_id"]
        else:
            cid = None
    oid = as_id(owner_person_id)
    oname = ""
    if oid:
        row = c.execute("SELECT name FROM people WHERE id=? AND active=1", (oid,)).fetchone()
        oname = row["name"] if row else ""
        oid = oid if row else None
    return aid, pid, cid, oid, oname

@app.post("/actions/add")
def add_action(request: Request, description: str = Form(...), avl_id: str = Form(""),
               product_id: str = Form(""), checklist_item_id: str = Form(""),
               owner_person_id: str = Form(""), owner_other: str = Form(""),
               due_date: str = Form(""), priority: str = Form("Normal"),
               call_id: str = Form(""), user=Depends(require_editor)):
    desc = description.strip()
    if not desc:
        return RedirectResponse("/actions", status_code=303)
    if priority not in db.ACTION_PRIORITIES:
        priority = "Normal"
    c = db.conn()
    aid, pid, cid, oid, oname = _action_fields(c, avl_id, product_id, checklist_item_id,
                                               owner_person_id)
    c.execute("INSERT INTO actions(avl_id, product_id, checklist_item_id, call_id, description, "
              "owner, owner_person_id, due_date, priority, created_by, created_at) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (aid, pid, cid, int(call_id) if call_id.strip().isdigit() else None, desc,
               oname or owner_other.strip(), oid, due_date, priority, user["email"], now()))
    c.commit(); c.close()
    db.log(user["email"], "action:add", desc[:80])
    return RedirectResponse(f"/actions?avl={aid or 0}", status_code=303)

@app.post("/actions/{aid_}/save")
def save_action(aid_: int, request: Request, description: str = Form(...), avl_id: str = Form(""),
                product_id: str = Form(""), checklist_item_id: str = Form(""),
                owner_person_id: str = Form(""), owner_other: str = Form(""),
                due_date: str = Form(""), priority: str = Form("Normal"),
                user=Depends(require_editor)):
    desc = description.strip()
    if priority not in db.ACTION_PRIORITIES:
        priority = "Normal"
    c = db.conn()
    if not desc or not c.execute("SELECT 1 FROM actions WHERE id=?", (aid_,)).fetchone():
        c.close()
        return RedirectResponse("/actions", status_code=303)
    aid, pid, cid, oid, oname = _action_fields(c, avl_id, product_id, checklist_item_id,
                                               owner_person_id)
    prev = c.execute("SELECT owner FROM actions WHERE id=?", (aid_,)).fetchone()
    owner_txt = oname or owner_other.strip() or (prev["owner"] if prev and not oid else "")
    c.execute("UPDATE actions SET avl_id=?, product_id=?, checklist_item_id=?, description=?, "
              "owner=?, owner_person_id=?, due_date=?, priority=? WHERE id=?",
              (aid, pid, cid, desc, owner_txt, oid, due_date, priority, aid_))
    c.commit(); c.close()
    db.log(user["email"], "action:save", desc[:80])
    return RedirectResponse(f"/actions?avl={aid or 0}", status_code=303)

@app.post("/actions/{aid}/done")
def action_done(aid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE actions SET status='Done', closed_at=? WHERE id=?", (now(), aid))
    row = c.execute("SELECT description FROM actions WHERE id=?", (aid,)).fetchone()
    c.commit(); c.close()
    db.log(user["email"], "action:done", (row["description"][:80] if row else str(aid)))
    return RedirectResponse("/actions", status_code=303)

@app.post("/actions/{aid}/reopen")
def action_reopen(aid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE actions SET status='Open', closed_at=NULL WHERE id=?", (aid,))
    row = c.execute("SELECT description FROM actions WHERE id=?", (aid,)).fetchone()
    c.commit(); c.close()
    db.log(user["email"], "action:reopen", (row["description"][:80] if row else str(aid)))
    return RedirectResponse("/actions?show=all", status_code=303)

@app.post("/actions/{aid}/delete")
def action_delete(aid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT description FROM actions WHERE id=?", (aid,)).fetchone()
    c.execute("DELETE FROM actions WHERE id=?", (aid,))
    c.commit(); c.close()
    if row:
        db.log(user["email"], "action:delete", row["description"][:80])
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
def _checklist_atts(c, item_ids):
    """Attachments grouped by the checklist item they document."""
    out = {}
    if not item_ids:
        return out
    qs = ",".join("?" * len(item_ids))
    for r in c.execute(f"SELECT * FROM attachments WHERE kind='checklist' AND ref_id IN ({qs}) "
                       "ORDER BY id DESC", item_ids):
        out.setdefault(r["ref_id"], []).append(r)
    return out

@app.get("/dataroom", response_class=HTMLResponse)
def dataroom(request: Request, product: int = 0, avl: int = 0, only: str = "",
             user=Depends(require_user)):
    c = db.conn()
    products = c.execute("SELECT id, name, category FROM products WHERE active=1 "
                         "ORDER BY category, name").fetchall()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    product = product or (products[0]["id"] if products else 0)
    avl = avl or (avls[0]["id"] if avls else 0)
    prow = c.execute("SELECT * FROM products WHERE id=?", (product,)).fetchone()
    category = prow["category"] if prow else ""
    q = "SELECT * FROM checklist_items WHERE product_id=? AND avl_id=? "
    params = [product, avl]
    if only in db.OBLIGATIONS:
        q += "AND obligation=? "
        params.append(only)
    elif only == "open":
        q += "AND status NOT IN ('Complete','TBD') "
    items = c.execute(q + "ORDER BY sort_order, id", params).fetchall()
    tmpls = db.templates_for(c, category, avl)
    atts = _checklist_atts(c, [i["id"] for i in items])

    # Group into the tracker's Document Categories, with a per-group rollup.
    # The filtered view must not distort the tracker, so the rollup is always
    # computed over the whole checklist.
    all_items = items if not only else c.execute(
        "SELECT * FROM checklist_items WHERE product_id=? AND avl_id=? ORDER BY sort_order, id",
        (product, avl)).fetchall()
    all_atts = atts if not only else _checklist_atts(c, [i["id"] for i in all_items])

    groups, seen = [], {}
    for i in items:
        key = i["doc_category"] or "Other"
        if key not in seen:
            seen[key] = {"name": key, "items": []}
            groups.append(seen[key])
        seen[key]["items"].append(i)

    # Status tracker: one row per document category over the full checklist.
    track, tseen = [], {}
    for i in all_items:
        key = i["doc_category"] or "Other"
        if key not in tseen:
            tseen[key] = {"name": key, "n": 0, "req": 0, "done": 0, "wip": 0, "blocked": 0,
                          "open": 0, "files": 0, "nofile_req": 0}
            track.append(tseen[key])
        t = tseen[key]
        t["n"] += 1
        n_files = len(all_atts.get(i["id"], []))
        t["files"] += n_files
        required = i["obligation"] == "Required"
        if required:
            t["req"] += 1
        if i["status"] == "Complete":
            t["done"] += required
        elif i["status"] == "Blocked":
            t["blocked"] += 1
        elif i["status"] == "In Progress":
            t["wip"] += 1
        elif i["status"] == "Not Started":
            t["open"] += 1
        if required and not n_files:
            t["nofile_req"] += 1
    for t in track:
        t["pct"] = round(100 * t["done"] / t["req"]) if t["req"] else None
    totals = {k: sum(t[k] for t in track) for k in
              ("n", "req", "done", "wip", "blocked", "open", "files", "nofile_req")}
    totals["pct"] = round(100 * totals["done"] / totals["req"]) if totals["req"] else None
    total_req, total_done = totals["req"], totals["done"]
    c.close()
    return templates.TemplateResponse(request, "dataroom.html", {"user": user, "products": products,
        "avls": avls, "items": items, "groups": groups, "sel_p": product, "sel_a": avl,
        "check_statuses": db.CHECK_STATUSES, "obligations": db.OBLIGATIONS,
        "templates_": tmpls, "category": category, "atts": atts, "only": only,
        "total_req": total_req, "total_done": total_done, "track": track, "totals": totals})

@app.post("/dataroom/seed")
def dataroom_seed(request: Request, product_id: int = Form(...), avl_id: int = Form(...),
                  template_id: int = Form(0), mode: str = Form("replace"),
                  user=Depends(require_editor)):
    """Apply a workstream template to one product x AVL checklist.

    mode=replace wipes rows that were never touched and re-seeds; mode=merge only
    adds workstreams that are missing, so in-flight status/notes survive.
    """
    c = db.conn()
    t = c.execute("SELECT * FROM workstream_templates WHERE id=?", (template_id,)).fetchone()
    if not t:
        c.close()
        return RedirectResponse(f"/dataroom?product={product_id}&avl={avl_id}", status_code=303)
    rows = c.execute("SELECT doc_category, workstream, obligation, sort_order "
                     "FROM workstream_template_items WHERE template_id=? "
                     "ORDER BY sort_order, id", (template_id,)).fetchall()
    if mode == "replace":
        # Keep anything a human has already worked on; only clear untouched rows.
        c.execute("DELETE FROM checklist_items WHERE product_id=? AND avl_id=? "
                  "AND status='Not Started' AND COALESCE(notes,'')='' AND COALESCE(pct,'')='' "
                  "AND COALESCE(eta,'')='' AND COALESCE(owner,'')='' "
                  "AND id NOT IN (SELECT ref_id FROM attachments WHERE kind='checklist')",
                  (product_id, avl_id))
    have = {r["workstream"] for r in c.execute(
        "SELECT workstream FROM checklist_items WHERE product_id=? AND avl_id=?",
        (product_id, avl_id))}
    added = 0
    for r in rows:
        if r["workstream"] in have:
            continue
        c.execute("INSERT INTO checklist_items(product_id, avl_id, doc_category, workstream, "
                  "obligation, sort_order, template_id, updated_by, updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?)",
                  (product_id, avl_id, r["doc_category"], r["workstream"], r["obligation"],
                   r["sort_order"], template_id, user["email"], now()))
        added += 1
    c.commit(); c.close()
    db.log(user["email"], "dataroom:seed", f"p{product_id}/a{avl_id} <- '{t['name']}' ({mode}, +{added})")
    return RedirectResponse(f"/dataroom?product={product_id}&avl={avl_id}", status_code=303)

@app.post("/dataroom/item/add")
def dataroom_item_add(request: Request, product_id: int = Form(...), avl_id: int = Form(...),
                      workstream: str = Form(...), doc_category: str = Form(""),
                      obligation: str = Form("Required"), user=Depends(require_editor)):
    """One-off requirement this TPO asked for that is not in any template."""
    ws = workstream.strip()
    if obligation not in db.OBLIGATIONS:
        obligation = "Required"
    if ws:
        c = db.conn()
        nxt = c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM checklist_items "
                        "WHERE product_id=? AND avl_id=?", (product_id, avl_id)).fetchone()[0]
        c.execute("INSERT INTO checklist_items(product_id, avl_id, doc_category, workstream, "
                  "obligation, sort_order, updated_by, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                  (product_id, avl_id, doc_category.strip(), ws, obligation, nxt,
                   user["email"], now()))
        c.commit(); c.close()
        db.log(user["email"], "dataroom:item:add", f"p{product_id}/a{avl_id} {ws}")
    return RedirectResponse(f"/dataroom?product={product_id}&avl={avl_id}", status_code=303)

@app.post("/dataroom/item/{iid}/delete")
def dataroom_item_delete(iid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT * FROM checklist_items WHERE id=?", (iid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/dataroom", status_code=303)
    n_files = c.execute("SELECT COUNT(*) FROM attachments WHERE kind='checklist' AND ref_id=?",
                        (iid,)).fetchone()[0]
    if n_files:
        # Files would be orphaned; make the user move them first.
        c.close()
        return RedirectResponse(f"/dataroom?product={row['product_id']}&avl={row['avl_id']}"
                                f"&err=files", status_code=303)
    c.execute("DELETE FROM checklist_items WHERE id=?", (iid,))
    c.commit(); c.close()
    db.log(user["email"], "dataroom:item:delete", row["workstream"])
    return RedirectResponse(f"/dataroom?product={row['product_id']}&avl={row['avl_id']}",
                            status_code=303)

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

# ---------------- 5b) workstream template management ----------------
@app.get("/workstreams", response_class=HTMLResponse)
def workstreams(request: Request, t: int = 0, user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    tmpls = c.execute("SELECT t.*, a.name AS avl_name, "
                      "(SELECT COUNT(*) FROM workstream_template_items i WHERE i.template_id=t.id) AS n_items "
                      "FROM workstream_templates t LEFT JOIN avls a ON a.id=t.avl_id "
                      "ORDER BY t.active DESC, t.category, t.name").fetchall()
    sel = t or (tmpls[0]["id"] if tmpls else 0)
    cur = c.execute("SELECT t.*, a.name AS avl_name FROM workstream_templates t "
                    "LEFT JOIN avls a ON a.id=t.avl_id WHERE t.id=?", (sel,)).fetchone()
    items = c.execute("SELECT * FROM workstream_template_items WHERE template_id=? "
                      "ORDER BY sort_order, id", (sel,)).fetchall() if cur else []
    doc_cats = [r[0] for r in c.execute(
        "SELECT DISTINCT doc_category FROM workstream_template_items "
        "WHERE doc_category<>'' ORDER BY doc_category")]
    # Where is this template already in play?
    history = c.execute("SELECT * FROM template_revisions WHERE template_id=? "
                        "ORDER BY id DESC LIMIT 15", (sel,)).fetchall() if cur else []
    usage = c.execute("SELECT p.name AS product, a.name AS avl_name, COUNT(*) AS n "
                      "FROM checklist_items ci JOIN products p ON p.id=ci.product_id "
                      "JOIN avls a ON a.id=ci.avl_id WHERE ci.template_id=? "
                      "GROUP BY ci.product_id, ci.avl_id ORDER BY p.name", (sel,)).fetchall() if cur else []
    c.close()
    return templates.TemplateResponse(request, "workstreams.html", {"user": user, "tmpls": tmpls,
        "cur": cur, "items": items, "avls": avls, "categories": db.CATEGORIES, "usage": usage,
        "obligations": db.OBLIGATIONS, "doc_cats": doc_cats, "history": history})

@app.post("/workstreams/add")
def ws_template_add(request: Request, name: str = Form(...), category: str = Form(""),
                    avl_id: str = Form(""), notes: str = Form(""), source_url: str = Form(""),
                    copy_from: str = Form(""), user=Depends(require_editor)):
    nm = name.strip()
    if not nm:
        return RedirectResponse("/workstreams", status_code=303)
    if category and category not in db.CATEGORIES:
        category = ""
    aid = int(avl_id) if avl_id.strip().isdigit() else None
    c = db.conn()
    if c.execute("SELECT 1 FROM workstream_templates WHERE name=?", (nm,)).fetchone():
        c.close()
        return RedirectResponse("/workstreams?err=dup", status_code=303)
    c.execute("INSERT INTO workstream_templates(name, category, avl_id, notes, source_url, "
              "created_by, created_at) VALUES(?,?,?,?,?,?,?)",
              (nm, category, aid, notes.strip(), source_url.strip(), user["email"], now()))
    tid = c.execute("SELECT id FROM workstream_templates WHERE name=?", (nm,)).fetchone()["id"]
    if copy_from.strip().isdigit():
        c.execute("INSERT INTO workstream_template_items(template_id, doc_category, workstream, "
                  "obligation, description, sort_order) "
                  "SELECT ?, doc_category, workstream, obligation, description, sort_order "
                  "FROM workstream_template_items WHERE template_id=?", (tid, int(copy_from)))
    c.commit(); c.close()
    db.log(user["email"], "workstream:template:add", f"{nm} [{category or 'any'}/{aid or 'any AVL'}]")
    return RedirectResponse(f"/workstreams?t={tid}", status_code=303)

@app.post("/workstreams/{tid}/edit")
def ws_template_edit(tid: int, request: Request, name: str = Form(...), category: str = Form(""),
                     avl_id: str = Form(""), notes: str = Form(""), source_url: str = Form(""),
                     user=Depends(require_editor)):
    nm = name.strip()
    if not nm:
        return RedirectResponse(f"/workstreams?t={tid}", status_code=303)
    if category and category not in db.CATEGORIES:
        category = ""
    aid = int(avl_id) if avl_id.strip().isdigit() else None
    c = db.conn()
    if c.execute("SELECT 1 FROM workstream_templates WHERE name=? AND id<>?", (nm, tid)).fetchone():
        c.close()
        return RedirectResponse(f"/workstreams?t={tid}&err=dup", status_code=303)
    db.record_revision(c, tid, "scope", f"renamed/rescoped to '{nm}'", user["email"])
    c.execute("UPDATE workstream_templates SET name=?, category=?, avl_id=?, notes=?, source_url=? "
              "WHERE id=?", (nm, category, aid, notes.strip(), source_url.strip(), tid))
    c.commit(); c.close()
    db.log(user["email"], "workstream:template:edit", f"{nm} [{category or 'any'}/{aid or 'any AVL'}]")
    return RedirectResponse(f"/workstreams?t={tid}", status_code=303)

@app.post("/workstreams/{tid}/toggle")
def ws_template_toggle(tid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    db.record_revision(c, tid, "retire/restore", "", user["email"])
    c.execute("UPDATE workstream_templates SET active = 1 - active WHERE id=?", (tid,))
    row = c.execute("SELECT name, active FROM workstream_templates WHERE id=?", (tid,)).fetchone()
    c.commit(); c.close()
    db.log(user["email"], "workstream:template:toggle",
           f"{row['name']} -> {'active' if row['active'] else 'retired'}")
    return RedirectResponse(f"/workstreams?t={tid}", status_code=303)

@app.post("/workstreams/{tid}/delete")
def ws_template_delete(tid: int, request: Request, user=Depends(require_admin)):
    c = db.conn()
    row = c.execute("SELECT name FROM workstream_templates WHERE id=?", (tid,)).fetchone()
    c.execute("DELETE FROM workstream_templates WHERE id=?", (tid,))
    c.commit(); c.close()
    if row:
        db.log(user["email"], "workstream:template:delete", row["name"])
    return RedirectResponse("/workstreams", status_code=303)

@app.post("/workstreams/undo/{rev_id}")
def ws_undo(rev_id: int, request: Request, user=Depends(require_editor)):
    """Roll a template back to how it was before one recorded change."""
    c = db.conn()
    res = db.restore_revision(c, rev_id, user["email"])
    if not res:
        c.close()
        return RedirectResponse("/workstreams?err=gone", status_code=303)
    tid, action = res
    c.commit(); c.close()
    db.log(user["email"], "workstream:undo", f"t{tid}: reverted '{action}'")
    return RedirectResponse(f"/workstreams?t={tid}&undone={action}", status_code=303)

@app.post("/workstreams/{tid}/items/add")
def ws_item_add(tid: int, request: Request, workstream: str = Form(...),
                doc_category: str = Form(""), obligation: str = Form("Required"),
                description: str = Form(""), user=Depends(require_editor)):
    ws = workstream.strip()
    if obligation not in db.OBLIGATIONS:
        obligation = "Required"
    if ws:
        c = db.conn()
        nxt = c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM workstream_template_items "
                        "WHERE template_id=?", (tid,)).fetchone()[0]
        db.record_revision(c, tid, "add requirement", ws, user["email"])
        c.execute("INSERT INTO workstream_template_items(template_id, doc_category, workstream, "
                  "obligation, description, sort_order) VALUES(?,?,?,?,?,?)",
                  (tid, doc_category.strip(), ws, obligation, description.strip(), nxt))
        c.commit(); c.close()
        db.log(user["email"], "workstream:item:add", f"t{tid} {ws}")
    return RedirectResponse(f"/workstreams?t={tid}", status_code=303)

@app.post("/workstreams/items/{iid}/save")
def ws_item_save(iid: int, request: Request, workstream: str = Form(...),
                 doc_category: str = Form(""), obligation: str = Form("Required"),
                 description: str = Form(""), sort_order: int = Form(0),
                 user=Depends(require_editor)):
    if obligation not in db.OBLIGATIONS:
        obligation = "Required"
    c = db.conn()
    row0 = c.execute("SELECT template_id, workstream FROM workstream_template_items WHERE id=?",
                     (iid,)).fetchone()
    if not row0:
        c.close()
        return RedirectResponse("/workstreams", status_code=303)
    tid = row0["template_id"]
    db.record_revision(c, tid, "edit requirement", row0["workstream"], user["email"])
    c.execute("UPDATE workstream_template_items SET doc_category=?, workstream=?, obligation=?, "
              "description=?, sort_order=? WHERE id=?",
              (doc_category.strip(), workstream.strip(), obligation, description.strip(),
               sort_order, iid))
    c.commit(); c.close()
    db.log(user["email"], "workstream:item:save", workstream.strip())
    return RedirectResponse(f"/workstreams?t={tid}", status_code=303)

@app.post("/workstreams/items/{iid}/delete")
def ws_item_delete(iid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT * FROM workstream_template_items WHERE id=?", (iid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/workstreams", status_code=303)
    db.record_revision(c, row["template_id"], "delete requirement", row["workstream"], user["email"])
    c.execute("DELETE FROM workstream_template_items WHERE id=?", (iid,))
    c.commit(); c.close()
    db.log(user["email"], "workstream:item:delete", row["workstream"])
    return RedirectResponse(f"/workstreams?t={row['template_id']}", status_code=303)

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
ATT_KINDS = ("product", "avl", "call", "checklist", "ie_item")

def _checklist_targets(c):
    """Every product x AVL x workstream row a file can be filed against."""
    return c.execute(
        "SELECT ci.id, ci.workstream, ci.status, ci.doc_category, ci.obligation, "
        "ci.product_id, ci.avl_id, p.name AS product, a.name AS avl_name "
        "FROM checklist_items ci JOIN products p ON p.id=ci.product_id "
        "JOIN avls a ON a.id=ci.avl_id "
        "ORDER BY a.name, p.name, ci.sort_order, ci.id").fetchall()

def _ie_targets(c):
    """Every IE report item a file can be filed against, plus a picker tree."""
    rows = c.execute(
        "SELECT i.id, i.item_id, i.sub_section, i.review_item, i.status, i.section_id, "
        "s.title AS section, s.sort_order AS s_ord, r.id AS report_id, r.name AS report, "
        "r.reviewer, p.name AS product "
        "FROM ie_report_items i JOIN ie_report_sections s ON s.id=i.section_id "
        "JOIN ie_reports r ON r.id=i.report_id JOIN products p ON p.id=r.product_id "
        "WHERE r.active=1 ORDER BY r.id, s.sort_order, i.sort_order, i.id").fetchall()
    tree, reports, sections = {}, [], {}
    for r in rows:
        rk, sk = str(r["report_id"]), str(r["section_id"])
        if rk not in tree:
            tree[rk] = {}
            reports.append([r["report_id"], f"{r['product']} - {r['reviewer']}"])
        if sk not in tree[rk]:
            tree[rk][sk] = {"name": r["section"], "items": []}
            sections[sk] = r["section"]
        tree[rk][sk]["items"].append(
            {"id": r["id"], "label": f"{r['item_id']} {r['sub_section']}".strip(),
             "status": r["status"]})
    return rows, {"tree": tree, "reports": reports}

def _files_context(c):
    products = c.execute("SELECT id, name FROM products ORDER BY name").fetchall()
    avls = c.execute("SELECT id, name FROM avls ORDER BY name").fetchall()
    calls_ = c.execute("SELECT calls.id, call_date, a.name AS avl_name FROM calls "
                       "JOIN avls a ON a.id=calls.avl_id ORDER BY call_date DESC LIMIT 100").fetchall()
    checks = _checklist_targets(c)
    ie_rows, ie_picker = _ie_targets(c)
    names = {"ie_item": {r["id"]: f"{r['product']} / {r['reviewer']} - {r['section']} / "
                                  f"{r['item_id']} {r['sub_section']}".strip() for r in ie_rows},
             "product": {p["id"]: p["name"] for p in products},
             "avl": {a["id"]: a["name"] for a in avls},
             "call": {r["id"]: f"{r['avl_name']} {r['call_date']}" for r in calls_},
             "checklist": {r["id"]: f"{r['avl_name']} / {r['product']} - "
                                    f"{r['doc_category'] + ': ' if r['doc_category'] else ''}"
                                    f"{r['workstream']}" for r in checks}}
    # Cascading picker data for the upload form: avl -> product -> [checklist rows]
    tree = {}
    for r in checks:
        tree.setdefault(str(r["avl_id"]), {}).setdefault(str(r["product_id"]), []).append(
            {"id": r["id"], "ws": r["workstream"], "status": r["status"],
             "cat": r["doc_category"]})
    picker = {"tree": tree,
              "avls": [[a["id"], a["name"]] for a in avls if str(a["id"]) in tree],
              "prods": {str(p["id"]): p["name"] for p in products}}
    return products, avls, calls_, checks, names, picker, ie_rows, ie_picker

@app.get("/files", response_class=HTMLResponse)
def files(request: Request, kind: str = "", ref: int = 0, user=Depends(require_user)):
    c = db.conn()
    products, avls, calls_, checks, names, picker, ie_rows, ie_picker = _files_context(c)
    q = "SELECT * FROM attachments"
    params = []
    if kind in ATT_KINDS:
        q += " WHERE kind=?"
        params.append(kind)
        if ref:
            q += " AND ref_id=?"
            params.append(ref)
    atts = c.execute(q + " ORDER BY id DESC", params).fetchall()
    # How many files sit under each bundle target, so the download side can say
    # up front whether there is anything to fetch.
    counts = {"product": {}, "avl": {}, "call": {}, "checklist": {}}
    for r in c.execute("SELECT kind, ref_id, COUNT(*) n FROM attachments GROUP BY kind, ref_id"):
        counts.setdefault(r["kind"], {})[r["ref_id"]] = r["n"]
    n_checklists = c.execute("SELECT COUNT(*) FROM (SELECT 1 FROM checklist_items "
                             "GROUP BY product_id, avl_id)").fetchone()[0]
    n_combos = c.execute("SELECT (SELECT COUNT(*) FROM avls WHERE active=1) * "
                         "(SELECT COUNT(*) FROM products WHERE active=1)").fetchone()[0]
    c.close()
    return templates.TemplateResponse(request, "files.html", {"user": user, "products": products,
        "avls": avls, "calls": calls_, "checks": checks, "atts": atts, "names": names,
        "picker": picker, "f_kind": kind, "f_ref": ref, "bundle_kinds": BUNDLE_KINDS,
        "ie_rows": ie_rows, "ie_picker": ie_picker, "ie_bundle_kinds": IE_BUNDLE_KINDS,
        "counts": counts, "n_checklists": n_checklists, "n_combos": n_combos})

@app.post("/files/upload")
async def upload(request: Request, kind: str = Form(...), ref_id: int = Form(...),
                 f: UploadFile = File(...), next_url: str = Form(""),
                 user=Depends(require_editor)):
    dest = next_url if next_url.startswith("/") else "/files"
    if kind not in ATT_KINDS:
        return RedirectResponse(dest, status_code=303)
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
    return RedirectResponse(dest, status_code=303)

@app.post("/files/{att_id}/reassign")
def reassign(att_id: int, request: Request, target: str = Form(...),
             next_url: str = Form(""), user=Depends(require_editor)):
    """Re-file an attachment onto a different AVL / product / workstream requirement.

    `target` is "<kind>:<id>" so the kind and the row always move together.
    """
    dest = next_url if next_url.startswith("/") else "/files"
    kind, _, rid = target.partition(":")
    if kind not in ATT_KINDS or not rid.isdigit():
        return RedirectResponse(dest, status_code=303)
    ref_id = int(rid)
    c = db.conn()
    row = c.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse(dest, status_code=303)
    table = {"product": "products", "avl": "avls", "call": "calls", "checklist": "checklist_items"}[kind]
    if not c.execute(f"SELECT 1 FROM {table} WHERE id=?", (ref_id,)).fetchone():
        c.close()
        return RedirectResponse(dest + ("&" if "?" in dest else "?") + "err=badref", status_code=303)
    c.execute("UPDATE attachments SET kind=?, ref_id=? WHERE id=?", (kind, ref_id, att_id))
    c.commit(); c.close()
    db.log(user["email"], "file:reassign",
           f"{row['filename']}: {row['kind']}#{row['ref_id']} -> {kind}#{ref_id}")
    return RedirectResponse(dest, status_code=303)

@app.post("/files/{att_id}/delete")
def delete_file(att_id: int, request: Request, next_url: str = Form(""),
                user=Depends(require_editor)):
    dest = next_url if next_url.startswith("/") else "/files"
    c = db.conn()
    row = c.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    if row:
        c.execute("DELETE FROM attachments WHERE id=?", (att_id,))
        c.commit()
        try:
            os.remove(row["stored_path"])
        except OSError:
            pass
        db.log(user["email"], "file:delete", row["filename"])
    c.close()
    return RedirectResponse(dest, status_code=303)

BUNDLE_KINDS = {
    "checklist": "One workstream requirement",
    "product": "Product (files filed at product level)",
    "avl": "TPO AVL (files filed at AVL level)",
    "call": "Call",
    "product_all": "Everything for a product (all AVLs)",
    "avl_all": "Everything for a TPO AVL (all products + calls)",
}
IE_BUNDLE_KINDS = {
    "ie_item": "One IE review item",
    "ie_section": "One IE report section",
    "ie_report": "Whole IE report (evidence pack)",
}

def _bundle_files(c, kind, ref_id):
    """(label, [(folder, attachment_row)]) for a download bundle."""
    def plain(k, table, col="name"):
        row = c.execute(f"SELECT {col} AS n FROM {table} WHERE id=?", (ref_id,)).fetchone()
        if not row:
            return None, []
        atts = c.execute("SELECT * FROM attachments WHERE kind=? AND ref_id=? ORDER BY id",
                         (k, ref_id)).fetchall()
        return row["n"], [("", a) for a in atts]

    if kind == "product":
        return plain("product", "products")
    if kind == "avl":
        return plain("avl", "avls")
    if kind == "call":
        row = c.execute("SELECT calls.call_date, a.name AS avl_name FROM calls "
                        "JOIN avls a ON a.id=calls.avl_id WHERE calls.id=?", (ref_id,)).fetchone()
        if not row:
            return None, []
        atts = c.execute("SELECT * FROM attachments WHERE kind='call' AND ref_id=? ORDER BY id",
                         (ref_id,)).fetchall()
        return f"{row['avl_name']} {row['call_date']}", [("", a) for a in atts]
    if kind == "checklist":
        row = c.execute("SELECT ci.*, p.name AS product, a.name AS avl_name FROM checklist_items ci "
                        "JOIN products p ON p.id=ci.product_id JOIN avls a ON a.id=ci.avl_id "
                        "WHERE ci.id=?", (ref_id,)).fetchone()
        if not row:
            return None, []
        atts = c.execute("SELECT * FROM attachments WHERE kind='checklist' AND ref_id=? ORDER BY id",
                         (ref_id,)).fetchall()
        return f"{row['avl_name']} {row['product']} - {row['workstream']}", [("", a) for a in atts]

    if kind == "ie_item":
        row = c.execute("SELECT i.item_id, i.sub_section, s.title AS section, p.name AS product "
                        "FROM ie_report_items i JOIN ie_report_sections s ON s.id=i.section_id "
                        "JOIN ie_reports r ON r.id=i.report_id JOIN products p ON p.id=r.product_id "
                        "WHERE i.id=?", (ref_id,)).fetchone()
        if not row:
            return None, []
        atts = c.execute("SELECT * FROM attachments WHERE kind='ie_item' AND ref_id=? ORDER BY id",
                         (ref_id,)).fetchall()
        return f"{row['product']} {row['section']} {row['item_id']}", [("", a) for a in atts]

    out = []
    if kind in ("ie_section", "ie_report"):
        if kind == "ie_section":
            head = c.execute("SELECT s.title AS n, p.name AS product FROM ie_report_sections s "
                             "JOIN ie_reports r ON r.id=s.report_id JOIN products p ON p.id=r.product_id "
                             "WHERE s.id=?", (ref_id,)).fetchone()
            where, args = "s.id=?", (ref_id,)
        else:
            head = c.execute("SELECT r.name AS n, p.name AS product FROM ie_reports r "
                             "JOIN products p ON p.id=r.product_id WHERE r.id=?", (ref_id,)).fetchone()
            where, args = "r.id=?", (ref_id,)
        if not head:
            return None, []
        for r in c.execute(
                "SELECT att.*, s.title AS section, s.sort_order AS s_ord, i.item_id, i.sub_section "
                "FROM attachments att JOIN ie_report_items i ON i.id=att.ref_id "
                "JOIN ie_report_sections s ON s.id=i.section_id "
                "JOIN ie_reports r ON r.id=i.report_id "
                f"WHERE att.kind='ie_item' AND {where} ORDER BY s.sort_order, i.sort_order", args):
            folder = (f"{r['s_ord']+1:02d}_{r['section']}/{r['item_id']} {r['sub_section']}".strip()
                      if kind == "ie_report" else f"{r['item_id']} {r['sub_section']}".strip())
            out.append((folder, r))
        return head["n"], out

    # Roll-ups: everything filed anywhere under one product or one AVL.
    if kind == "product_all":
        row = c.execute("SELECT name FROM products WHERE id=?", (ref_id,)).fetchone()
        if not row:
            return None, []
        for a in c.execute("SELECT * FROM attachments WHERE kind='product' AND ref_id=? ORDER BY id",
                           (ref_id,)):
            out.append(("00_product-level", a))
        for r in c.execute(
                "SELECT att.*, av.name AS avl_name, ci.doc_category, ci.workstream "
                "FROM attachments att JOIN checklist_items ci ON ci.id=att.ref_id "
                "JOIN avls av ON av.id=ci.avl_id "
                "WHERE att.kind='checklist' AND ci.product_id=? ORDER BY av.name, ci.sort_order",
                (ref_id,)):
            out.append((f"{r['avl_name']}/{r['doc_category'] or 'Other'}", r))
        return row["name"], out

    if kind == "avl_all":
        row = c.execute("SELECT name FROM avls WHERE id=?", (ref_id,)).fetchone()
        if not row:
            return None, []
        for a in c.execute("SELECT * FROM attachments WHERE kind='avl' AND ref_id=? ORDER BY id",
                           (ref_id,)):
            out.append(("00_avl-level", a))
        for r in c.execute(
                "SELECT att.*, cl.call_date FROM attachments att JOIN calls cl ON cl.id=att.ref_id "
                "WHERE att.kind='call' AND cl.avl_id=? ORDER BY cl.call_date", (ref_id,)):
            out.append((f"01_calls/{r['call_date']}", r))
        for r in c.execute(
                "SELECT att.*, p.name AS product, ci.doc_category FROM attachments att "
                "JOIN checklist_items ci ON ci.id=att.ref_id JOIN products p ON p.id=ci.product_id "
                "WHERE att.kind='checklist' AND ci.avl_id=? ORDER BY p.name, ci.sort_order",
                (ref_id,)):
            out.append((f"{r['product']}/{r['doc_category'] or 'Other'}", r))
        return row["name"], out
    return None, []

@app.get("/files/bundle.zip")
def files_bundle(request: Request, kind: str = "", ref_id: int = 0, user=Depends(require_user)):
    """Download side of the uploader: the same targets, zipped with a manifest."""
    if (kind not in BUNDLE_KINDS and kind not in IE_BUNDLE_KINDS) or not ref_id:
        return RedirectResponse("/files?err=badtarget", status_code=303)
    c = db.conn()
    label, items = _bundle_files(c, kind, ref_id)
    c.close()
    if label is None:
        return RedirectResponse("/files?err=badtarget", status_code=303)
    if not items:
        return RedirectResponse(f"/files?err=empty&kind={kind}&ref={ref_id}", status_code=303)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{_safe(label, 60)}_{stamp}"
    path = os.path.join(PKG_DIR, base + ".zip")
    rows, missing = [], 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        seen = set()
        for folder, a in items:
            if not os.path.exists(a["stored_path"]):
                missing += 1
                rows.append([folder or "/", a["filename"], a["uploaded_by"],
                             (a["uploaded_at"] or "")[:16], "FILE NOT FOUND ON DISK"])
                continue
            arc = f"{_safe_path(folder)}/{_safe(a['filename'], 90)}" if folder else _safe(a["filename"], 90)
            n = 1
            while arc in seen:            # same filename twice under one folder
                stem, _, ext = arc.rpartition(".")
                arc = f"{stem}_{n}.{ext}" if stem else f"{arc}_{n}"
                n += 1
            seen.add(arc)
            z.write(a["stored_path"], arc)
            rows.append([folder or "/", a["filename"], a["uploaded_by"],
                         (a["uploaded_at"] or "")[:16], arc])
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Folder", "File", "Uploaded by", "Uploaded at", "Path in zip"])
        for r in rows:
            w.writerow(r)
        z.writestr("MANIFEST.csv", buf.getvalue())

    kind_label = {**BUNDLE_KINDS, **IE_BUNDLE_KINDS}[kind]
    db.log(user["email"], "files:bundle",
           f"{kind_label} '{label}' - {len(items) - missing} file(s)")
    return FileResponse(path, filename=base + ".zip", media_type="application/zip")

@app.get("/files/{att_id}/download")
def download(att_id: int, request: Request, user=Depends(require_user)):
    c = db.conn()
    row = c.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    c.close()
    if not row:
        return RedirectResponse("/files", status_code=303)
    return FileResponse(row["stored_path"], filename=row["filename"])

# ---------------- 10) TPO-side contacts ----------------
@app.get("/contacts", response_class=HTMLResponse)
def contacts(request: Request, avl: int = 0, show_inactive: int = 0, q: str = "",
             user=Depends(require_user)):
    c = db.conn()
    avls = c.execute("SELECT id, name, account_manager FROM avls WHERE active=1 ORDER BY name").fetchall()
    sql = ("SELECT ct.*, a.name AS avl_name FROM contacts ct JOIN avls a ON a.id=ct.avl_id WHERE 1=1 ")
    params = []
    if avl:
        sql += "AND ct.avl_id=? "
        params.append(avl)
    if not show_inactive:
        sql += "AND ct.active=1 "
    if q.strip():
        sql += "AND (ct.name LIKE ? OR ct.role LIKE ? OR ct.email LIKE ?) "
        params += [f"%{q.strip()}%"] * 3
    rows = c.execute(sql + "ORDER BY a.name, ct.active DESC, ct.is_primary DESC, ct.name",
                     params).fetchall()
    # Group by AVL so the page reads as an address book, and show the empty ones.
    groups, seen = [], {}
    for a in avls:
        if avl and a["id"] != avl:
            continue
        seen[a["id"]] = {"avl": a, "rows": []}
        groups.append(seen[a["id"]])
    for r in rows:
        if r["avl_id"] in seen:
            seen[r["avl_id"]]["rows"].append(r)
    n_live = sum(1 for r in rows if r["active"])
    c.close()
    return templates.TemplateResponse(request, "contacts.html", {"user": user, "avls": avls,
        "groups": groups, "sel_a": avl, "q": q, "show_inactive": show_inactive,
        "contact_roles": db.CONTACT_ROLES, "n_live": n_live})

@app.post("/contacts/add")
def contact_add(request: Request, avl_id: int = Form(...), name: str = Form(...),
                role: str = Form(""), email: str = Form(""), phone: str = Form(""),
                website: str = Form(""), notes: str = Form(""), is_primary: int = Form(0),
                user=Depends(require_editor)):
    nm = name.strip()
    if not nm:
        return RedirectResponse(f"/contacts?avl={avl_id}", status_code=303)
    c = db.conn()
    if is_primary:
        c.execute("UPDATE contacts SET is_primary=0 WHERE avl_id=?", (avl_id,))
    c.execute("INSERT INTO contacts(avl_id, name, role, email, phone, website, notes, is_primary, "
              "created_by, created_at, updated_by, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (avl_id, nm, role.strip(), email.strip().lower(), phone.strip(),
               db.normalize_website(website), notes.strip(), 1 if is_primary else 0,
               user["email"], now(), user["email"], now()))
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl_id,)).fetchone()["name"]
    c.commit(); c.close()
    db.log(user["email"], "contact:add", f"{nm} @ {aname}")
    return RedirectResponse(f"/contacts?avl={avl_id}", status_code=303)

@app.post("/contacts/{cid}/save")
def contact_save(cid: int, request: Request, name: str = Form(...), role: str = Form(""),
                 email: str = Form(""), phone: str = Form(""), website: str = Form(""),
                 notes: str = Form(""), user=Depends(require_editor)):
    nm = name.strip()
    c = db.conn()
    row = c.execute("SELECT avl_id FROM contacts WHERE id=?", (cid,)).fetchone()
    if not row or not nm:
        c.close()
        return RedirectResponse("/contacts", status_code=303)
    c.execute("UPDATE contacts SET name=?, role=?, email=?, phone=?, website=?, notes=?, "
              "updated_by=?, updated_at=? WHERE id=?",
              (nm, role.strip(), email.strip().lower(), phone.strip(),
               db.normalize_website(website), notes.strip(), user["email"], now(), cid))
    c.commit(); c.close()
    db.log(user["email"], "contact:save", nm)
    return RedirectResponse(f"/contacts?avl={row['avl_id']}", status_code=303)

@app.post("/contacts/{cid}/primary")
def contact_primary(cid: int, request: Request, user=Depends(require_editor)):
    """Exactly one primary point of contact per AVL."""
    c = db.conn()
    row = c.execute("SELECT avl_id, name, is_primary FROM contacts WHERE id=?", (cid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/contacts", status_code=303)
    c.execute("UPDATE contacts SET is_primary=0 WHERE avl_id=?", (row["avl_id"],))
    if not row["is_primary"]:
        c.execute("UPDATE contacts SET is_primary=1 WHERE id=?", (cid,))
    c.commit(); c.close()
    db.log(user["email"], "contact:primary",
           f"{row['name']}" + (" (cleared)" if row["is_primary"] else ""))
    return RedirectResponse(f"/contacts?avl={row['avl_id']}", status_code=303)

@app.post("/contacts/{cid}/toggle")
def contact_toggle(cid: int, request: Request, user=Depends(require_editor)):
    """Soft delete: people leave TPOs, but the call history should still name them."""
    c = db.conn()
    row = c.execute("SELECT avl_id, name, active FROM contacts WHERE id=?", (cid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/contacts", status_code=303)
    c.execute("UPDATE contacts SET active = 1 - active, is_primary = CASE WHEN active=1 THEN 0 "
              "ELSE is_primary END, updated_by=?, updated_at=? WHERE id=?",
              (user["email"], now(), cid))
    c.commit(); c.close()
    db.log(user["email"], "contact:toggle",
           f"{row['name']} -> {'inactive' if row['active'] else 'active'}")
    return RedirectResponse(f"/contacts?avl={row['avl_id']}", status_code=303)

@app.get("/contacts.csv")
def contacts_csv(request: Request, user=Depends(require_user)):
    c = db.conn()
    rows = c.execute("SELECT a.name AS avl_name, ct.name, ct.role, ct.email, ct.phone, ct.website, "
                     "ct.is_primary, ct.notes FROM contacts ct JOIN avls a ON a.id=ct.avl_id "
                     "WHERE ct.active=1 ORDER BY a.name, ct.is_primary DESC, ct.name").fetchall()
    c.close()
    return _csv_response([[r["avl_name"], r["name"], r["role"], r["email"], r["phone"],
                           r["website"], "Yes" if r["is_primary"] else "", r["notes"]] for r in rows],
                         ["TPO AVL", "Name", "Role", "Email", "Phone", "Website", "Primary", "Notes"],
                         "avl_contacts.csv")

# ---------------- 11) dataroom package builder ----------------
import zipfile, json

PKG_DIR = os.path.join(UPLOAD_DIR, "packages")
os.makedirs(PKG_DIR, exist_ok=True)

def _safe(name, limit=80):
    """One path segment, safe on Windows and macOS. & and , are legal, / is not."""
    s = _re.sub(r"[^A-Za-z0-9 ._()&,+-]", "_", (name or "").strip())
    return (_re.sub(r"_+", "_", s)[:limit] or "item").strip(" ._")

def _safe_path(path, limit=60):
    """Sanitise each segment so 'Product/Category' nests instead of flattening."""
    return "/".join(_safe(seg, limit) for seg in str(path or "").split("/") if seg.strip())

def _package_contents(c, product_id, avl_id, scope):
    """Every in-scope requirement with its files, in checklist order.

    Requirements with no file are kept and marked as gaps - the content list is
    only useful if it shows what is still missing.
    """
    frag, extra = db.scope_filter(scope)
    rows = c.execute("SELECT * FROM checklist_items WHERE product_id=? AND avl_id=? " + frag +
                     "ORDER BY sort_order, id", [product_id, avl_id] + extra).fetchall()
    atts = _checklist_atts(c, [r["id"] for r in rows])
    groups, seen = [], {}
    for r in rows:
        key = r["doc_category"] or "Other"
        if key not in seen:
            seen[key] = {"name": key, "items": []}
            groups.append(seen[key])
        files = atts.get(r["id"], [])
        seen[key]["items"].append({"row": r, "files": files, "gap": not files})
    return groups

def _dominant_template(c, product_id, avl_id):
    row = c.execute("SELECT template_id, COUNT(*) n FROM checklist_items "
                    "WHERE product_id=? AND avl_id=? AND template_id IS NOT NULL "
                    "GROUP BY template_id ORDER BY n DESC LIMIT 1", (product_id, avl_id)).fetchone()
    return row["template_id"] if row else None

def _template_drift(c, product_id, avl_id, template_id):
    """Template requirements that never made it onto this checklist.

    Seeding is a point-in-time copy, so a template edited afterwards leaves the
    checklist behind. Those are gaps too, and worth naming in a submission.
    """
    if not template_id:
        return []
    have = {r["workstream"] for r in c.execute(
        "SELECT workstream FROM checklist_items WHERE product_id=? AND avl_id=?",
        (product_id, avl_id))}
    return [r for r in c.execute(
        "SELECT doc_category, workstream, obligation, description "
        "FROM workstream_template_items WHERE template_id=? ORDER BY sort_order, id",
        (template_id,)) if r["workstream"] not in have]

def _package_stats(groups):
    n_reqs = sum(len(g["items"]) for g in groups)
    n_files = sum(len(i["files"]) for g in groups for i in g["items"])
    n_gaps = sum(1 for g in groups for i in g["items"] if i["gap"])
    blocking = sum(1 for g in groups for i in g["items"]
                   if i["gap"] and i["row"]["obligation"] == "Required")
    return {"n_reqs": n_reqs, "n_files": n_files, "n_gaps": n_gaps, "blocking": blocking}

@app.get("/dataroom/package", response_class=HTMLResponse)
def package_preview(request: Request, product: int = 0, avl: int = 0, scope: str = "all",
                    template: int = 0, user=Depends(require_user)):
    if scope not in db.PACKAGE_SCOPES:
        scope = "all"
    c = db.conn()
    products = c.execute("SELECT id, name, category FROM products WHERE active=1 "
                         "ORDER BY category, name").fetchall()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    product = product or (products[0]["id"] if products else 0)
    avl = avl or (avls[0]["id"] if avls else 0)
    groups = _package_contents(c, product, avl, scope)
    stats = _package_stats(groups)
    tmpl_id = template or _dominant_template(c, product, avl)
    drift = _template_drift(c, product, avl, tmpl_id)
    tmpl = c.execute("SELECT id, name FROM workstream_templates WHERE id=?", (tmpl_id,)).fetchone() \
           if tmpl_id else None
    all_tmpls = db.templates_for(c, "", avl) or c.execute(
        "SELECT id, name, category FROM workstream_templates WHERE active=1 ORDER BY name").fetchall()
    prior = c.execute("SELECT * FROM packages WHERE product_id=? AND avl_id=? "
                      "ORDER BY id DESC LIMIT 20", (product, avl)).fetchall()
    next_rev = (c.execute("SELECT COALESCE(MAX(revision), 0) + 1 AS n FROM packages "
                          "WHERE product_id=? AND avl_id=?", (product, avl)).fetchone()["n"])
    pname = c.execute("SELECT name FROM products WHERE id=?", (product,)).fetchone()
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl,)).fetchone()
    c.close()
    return templates.TemplateResponse(request, "package.html", {"user": user, "products": products,
        "avls": avls, "sel_p": product, "sel_a": avl, "scope": scope, "scopes": db.PACKAGE_SCOPES,
        "groups": groups, "stats": stats, "prior": prior, "drift": drift, "tmpl": tmpl,
        "all_tmpls": all_tmpls, "next_rev": next_rev, "today": datetime.date.today().isoformat(),
        "product_name": pname["name"] if pname else "", "avl_name": aname["name"] if aname else ""})

@app.post("/dataroom/package/build")
def package_build(request: Request, product_id: int = Form(...), avl_id: int = Form(...),
                  scope: str = Form("all"), label: str = Form(""), template_id: str = Form(""),
                  rev_date: str = Form(""), user=Depends(require_editor)):
    """Zip the attached files with a manifest and a dataroom summary.

    The summary compares the checklist against the template it was seeded from,
    so it names three things: what is included, what is on the checklist with no
    document, and what the template asks for that the checklist never picked up.
    """
    if scope not in db.PACKAGE_SCOPES:
        scope = "all"
    c = db.conn()
    groups = _package_contents(c, product_id, avl_id, scope)
    stats = _package_stats(groups)
    tid = int(template_id) if str(template_id).strip().isdigit() and int(template_id) > 0 \
          else _dominant_template(c, product_id, avl_id)
    drift = _template_drift(c, product_id, avl_id, tid)
    trow = c.execute("SELECT name FROM workstream_templates WHERE id=?", (tid,)).fetchone() if tid else None
    tname = trow["name"] if trow else "(no template recorded)"
    pname = c.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()["name"]
    aname = c.execute("SELECT name FROM avls WHERE id=?", (avl_id,)).fetchone()["name"]

    rev = c.execute("SELECT COALESCE(MAX(revision), 0) + 1 AS n FROM packages "
                    "WHERE product_id=? AND avl_id=?", (product_id, avl_id)).fetchone()["n"]
    rdate = rev_date.strip() or datetime.date.today().isoformat()
    rev_code = f"R{rev:02d}"
    stamp = rdate.replace("-", "")
    base = f"{_safe(aname, 30)}_{_safe(pname, 30)}_{rev_code}_{stamp}"
    stored = os.path.join(PKG_DIR, base + ".zip")
    full_code = f"{aname} / {pname} / {rev_code} / {rdate}"

    manifest_rows, summary_rows, missing_paths = [], [], []
    with zipfile.ZipFile(stored, "w", zipfile.ZIP_DEFLATED) as z:
        for gi, g in enumerate(groups, 1):
            folder = f"{gi:02d}_{_safe(g['name'], 50)}"
            for item in g["items"]:
                r = item["row"]
                if item["gap"]:
                    summary_rows.append([g["name"], r["workstream"], r["obligation"], r["status"],
                                         0, "NO DOCUMENT"])
                    manifest_rows.append([g["name"], r["workstream"], r["obligation"],
                                          r["status"], "", "MISSING - no file attached"])
                    continue
                sub = f"{folder}/{_safe(r['workstream'], 60)}"
                got = 0
                for f in item["files"]:
                    arc = f"{sub}/{_safe(f['filename'], 90)}"
                    if os.path.exists(f["stored_path"]):
                        z.write(f["stored_path"], arc)
                        got += 1
                        manifest_rows.append([g["name"], r["workstream"], r["obligation"],
                                              r["status"], arc, ""])
                    else:
                        missing_paths.append(f["filename"])
                        manifest_rows.append([g["name"], r["workstream"], r["obligation"],
                                              r["status"], "", "FILE NOT FOUND ON DISK"])
                summary_rows.append([g["name"], r["workstream"], r["obligation"], r["status"],
                                     got, "INCLUDED" if got else "NO DOCUMENT"])
        for d in drift:
            summary_rows.append([d["doc_category"], d["workstream"], d["obligation"],
                                 "-", 0, "NOT ON CHECKLIST"])

        def csv_bytes(header, rows):
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(header)
            for row in rows:
                w.writerow(row)
            return buf.getvalue()

        z.writestr("MANIFEST.csv", csv_bytes(
            ["Document Category", "Required Document", "Obligation", "Status",
             "File in package", "Gap"], manifest_rows))
        z.writestr("SUMMARY.csv", csv_bytes(
            ["Document Category", "Required Document", "Obligation", "Checklist status",
             "Files included", "Result"], summary_rows))

        # readable summary
        by_cat = {}
        for cat, req, obl, st_, n, res in summary_rows:
            d = by_cat.setdefault(cat or "Other", {"n": 0, "inc": 0, "nodoc": 0, "untracked": 0, "files": 0})
            d["n"] += 1
            d["files"] += n
            d["inc"] += res == "INCLUDED"
            d["nodoc"] += res == "NO DOCUMENT"
            d["untracked"] += res == "NOT ON CHECKLIST"
        L = [f"DATAROOM SUBMISSION SUMMARY",
             f"{'=' * 60}",
             f"TPO AVL          : {aname}",
             f"Product          : {pname}",
             f"Revision         : {rev_code}",
             f"Revision date    : {rdate}",
             f"Built            : {now()} by {user['email']}",
             f"Scope            : {db.PACKAGE_SCOPES[scope]}",
             f"Compared against : {tname}"]
        if label.strip():
            L.append(f"Label            : {label.strip()}")
        L += ["",
              f"{stats['n_files']} document(s) included against {stats['n_reqs']} requirement(s) in scope.",
              f"{stats['n_gaps']} requirement(s) have no document ({stats['blocking']} of them Required).",
              f"{len(drift)} template requirement(s) are not on this checklist yet.", "",
              "BY DOCUMENT CATEGORY", "-" * 60,
              f"{'Category':<38}{'Reqs':>5}{'Incl':>6}{'NoDoc':>7}{'NotTrk':>7}"]
        for cat, d in by_cat.items():
            L.append(f"{cat[:37]:<38}{d['n']:>5}{d['inc']:>6}{d['nodoc']:>7}{d['untracked']:>7}")
        tot = {k: sum(d[k] for d in by_cat.values()) for k in ("n", "inc", "nodoc", "untracked")}
        L += [f"{'TOTAL':<38}{tot['n']:>5}{tot['inc']:>6}{tot['nodoc']:>7}{tot['untracked']:>7}", ""]

        L += ["CONTENTS", "-" * 60]
        for gi, g in enumerate(groups, 1):
            got = sum(len(i["files"]) for i in g["items"])
            L.append(f"{gi:02d}. {g['name']}  -  {got} file(s)")
            for item in g["items"]:
                r = item["row"]
                mark = "  [ ] NO DOCUMENT" if item["gap"] else "  [x]"
                L.append(f"    {mark} ({r['obligation']}, {r['status']}) {r['workstream']}")
                for f in item["files"]:
                    L.append(f"          - {f['filename']}")
            L.append("")
        if drift:
            L += ["NOT ON THIS CHECKLIST", "-" * 60,
                  f"In '{tname}' but never seeded here. Re-apply the template on the Dataroom",
                  "page (Merge) to start tracking them.", ""]
            for d in drift:
                L.append(f"    [ ] ({d['obligation']}) {d['doc_category']}: {d['workstream']}")
            L.append("")
        if missing_paths:
            L += ["WARNING - recorded attachments whose file was not on disk:",
                  *[f"  - {m}" for m in missing_paths], ""]
        z.writestr("DATAROOM_SUMMARY.txt", "\n".join(L))

    size = os.path.getsize(stored)
    c.execute("INSERT INTO packages(product_id, avl_id, label, scope, n_files, n_reqs, n_gaps, "
              "n_untracked, bytes, stored_path, manifest, revision, rev_code, rev_date, "
              "template_id, created_by, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (product_id, avl_id, label.strip(), scope, stats["n_files"], stats["n_reqs"],
               stats["n_gaps"], len(drift), size, stored, json.dumps(manifest_rows), rev,
               rev_code, rdate, tid, user["email"], now()))
    c.execute("UPDATE packages SET superseded=1 WHERE product_id=? AND avl_id=? AND revision<?",
              (product_id, avl_id, rev))
    c.commit(); c.close()
    db.log(user["email"], "package:build",
           f"{full_code} [{scope}] {stats['n_files']} files, {stats['n_gaps']} gaps, "
           f"{len(drift)} untracked")
    return FileResponse(stored, filename=base + ".zip", media_type="application/zip")

@app.get("/dataroom/package/{pkg_id}/download")
def package_download(pkg_id: int, request: Request, user=Depends(require_user)):
    c = db.conn()
    row = c.execute("SELECT * FROM packages WHERE id=?", (pkg_id,)).fetchone()
    c.close()
    if not row or not os.path.exists(row["stored_path"]):
        return RedirectResponse("/dataroom/package?err=gone", status_code=303)
    return FileResponse(row["stored_path"], filename=os.path.basename(row["stored_path"]),
                        media_type="application/zip")

@app.get("/dataroom/package/{pkg_id}/manifest.csv")
def package_manifest(pkg_id: int, request: Request, user=Depends(require_user)):
    """The content list as sent, even if files have changed since."""
    c = db.conn()
    row = c.execute("SELECT * FROM packages WHERE id=?", (pkg_id,)).fetchone()
    c.close()
    if not row:
        return RedirectResponse("/dataroom/package", status_code=303)
    rows = json.loads(row["manifest"] or "[]")
    return _csv_response(rows, ["Document Category", "Required Document", "Obligation",
                                "Status", "File in package", "Gap"],
                         f"manifest_{pkg_id}.csv")

@app.post("/dataroom/package/{pkg_id}/delete")
def package_delete(pkg_id: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT * FROM packages WHERE id=?", (pkg_id,)).fetchone()
    if row:
        c.execute("DELETE FROM packages WHERE id=?", (pkg_id,))
        c.commit()
        try:
            os.remove(row["stored_path"])
        except OSError:
            pass
        db.log(user["email"], "package:delete", os.path.basename(row["stored_path"]))
    c.close()
    return RedirectResponse(f"/dataroom/package?product={row['product_id']}&avl={row['avl_id']}"
                            if row else "/dataroom/package", status_code=303)

# ---------------- 12) IE / DNV technology reviews ----------------
# Kept separate from the AVL workstream templates on purpose: an IE review is a
# document a third party writes about a product, not a per-TPO dataroom checklist.
IE_KIND = "ie_item"

def _ie_progress(c, report_id):
    """Per-section rollup plus totals for one report."""
    secs = c.execute("SELECT * FROM ie_report_sections WHERE report_id=? ORDER BY sort_order, id",
                     (report_id,)).fetchall()
    items = c.execute("SELECT * FROM ie_report_items WHERE report_id=? ORDER BY sort_order, id",
                      (report_id,)).fetchall()
    atts = {}
    if items:
        qs = ",".join("?" * len(items))
        for a in c.execute(f"SELECT * FROM attachments WHERE kind='{IE_KIND}' AND ref_id IN ({qs}) "
                           "ORDER BY id DESC", [i["id"] for i in items]):
            atts.setdefault(a["ref_id"], []).append(a)
    groups, by_sec = [], {}
    for s in secs:
        by_sec[s["id"]] = {"sec": s, "items": [], "n": 0, "done": 0, "wip": 0,
                           "blocked": 0, "open": 0, "files": 0, "crit_open": 0}
        groups.append(by_sec[s["id"]])
    for i in items:
        g = by_sec.get(i["section_id"])
        if not g:
            continue
        g["items"].append(i)
        g["n"] += 1
        g["files"] += len(atts.get(i["id"], []))
        st = i["status"]
        if st in ("Accepted", "N/A"):
            g["done"] += 1
        elif st == "Blocked":
            g["blocked"] += 1
        elif st in ("In Progress", "Submitted"):
            g["wip"] += 1
        else:
            g["open"] += 1
        if i["priority"] == "Critical" and st not in ("Accepted", "N/A"):
            g["crit_open"] += 1
    for g in groups:
        g["pct"] = round(100 * g["done"] / g["n"]) if g["n"] else 0
    totals = {k: sum(g[k] for g in groups) for k in
              ("n", "done", "wip", "blocked", "open", "files", "crit_open")}
    totals["pct"] = round(100 * totals["done"] / totals["n"]) if totals["n"] else 0
    return groups, totals, atts

@app.get("/ie", response_class=HTMLResponse)
def ie_home(request: Request, user=Depends(require_user)):
    c = db.conn()
    reports = c.execute(
        "SELECT r.*, p.name AS product, p.category, "
        "(SELECT COUNT(*) FROM ie_report_items i WHERE i.report_id=r.id) AS n_items, "
        "(SELECT COUNT(*) FROM ie_report_items i WHERE i.report_id=r.id "
        " AND i.status IN ('Accepted','N/A')) AS n_done "
        "FROM ie_reports r JOIN products p ON p.id=r.product_id "
        "WHERE r.active=1 ORDER BY r.id DESC").fetchall()
    tmpls = c.execute("SELECT t.*, "
                      "(SELECT COUNT(*) FROM ie_template_sections s WHERE s.template_id=t.id) AS n_sec, "
                      "(SELECT COUNT(*) FROM ie_template_items i JOIN ie_template_sections s "
                      " ON s.id=i.section_id WHERE s.template_id=t.id) AS n_items "
                      "FROM ie_templates t WHERE t.active=1 ORDER BY t.name").fetchall()
    products = c.execute("SELECT id, name, category FROM products WHERE active=1 "
                         "ORDER BY category, name").fetchall()
    c.close()
    return templates.TemplateResponse(request, "ie.html", {"user": user, "reports": reports,
        "tmpls": tmpls, "products": products, "reviewers": db.IE_REVIEWERS,
        "statuses": db.IE_REPORT_STATUSES})

@app.post("/ie/reports/add")
def ie_report_add(request: Request, product_id: int = Form(...), template_id: int = Form(...),
                  name: str = Form(""), reviewer: str = Form("DNV"),
                  kickoff_date: str = Form(""), target_date: str = Form(""),
                  user=Depends(require_editor)):
    c = db.conn()
    t = c.execute("SELECT * FROM ie_templates WHERE id=?", (template_id,)).fetchone()
    p = c.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()
    if not t or not p:
        c.close()
        return RedirectResponse("/ie?err=bad", status_code=303)
    rname = name.strip() or f"{p['name']} - {reviewer} Technology Review"
    c.execute("INSERT INTO ie_reports(product_id, template_id, name, reviewer, kickoff_date, "
              "target_date, created_by, created_at) VALUES(?,?,?,?,?,?,?,?)",
              (product_id, template_id, rname, reviewer, kickoff_date, target_date,
               user["email"], now()))
    rid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    for s in c.execute("SELECT * FROM ie_template_sections WHERE template_id=? "
                       "ORDER BY sort_order, id", (template_id,)).fetchall():
        c.execute("INSERT INTO ie_report_sections(report_id, code, title, owner, sort_order) "
                  "VALUES(?,?,?,?,?)", (rid, s["code"], s["title"], s["owner"], s["sort_order"]))
        sid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        for i in c.execute("SELECT * FROM ie_template_items WHERE section_id=? "
                           "ORDER BY sort_order, id", (s["id"],)).fetchall():
            c.execute("INSERT INTO ie_report_items(report_id, section_id, item_id, sub_section, "
                      "review_item, evidence, priority, source, owner, sort_order, "
                      "updated_by, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (rid, sid, i["item_id"], i["sub_section"], i["review_item"], i["evidence"],
                       i["priority"], i["source"], i["suggested_owner"], i["sort_order"],
                       user["email"], now()))
    c.commit(); c.close()
    db.log(user["email"], "ie:report:add", f"{rname} from '{t['name']}'")
    return RedirectResponse(f"/ie/report/{rid}", status_code=303)

@app.get("/ie/report/{rid}", response_class=HTMLResponse)
def ie_report(request: Request, rid: int, only: str = "", user=Depends(require_user)):
    c = db.conn()
    r = c.execute("SELECT r.*, p.name AS product, p.category FROM ie_reports r "
                  "JOIN products p ON p.id=r.product_id WHERE r.id=?", (rid,)).fetchone()
    if not r:
        c.close()
        return RedirectResponse("/ie", status_code=303)
    groups, totals, atts = _ie_progress(c, rid)
    if only:
        for g in groups:
            if only == "open":
                g["items"] = [i for i in g["items"] if i["status"] not in ("Accepted", "N/A")]
            elif only == "critical":
                g["items"] = [i for i in g["items"] if i["priority"] == "Critical"]
            elif only == "blocked":
                g["items"] = [i for i in g["items"] if i["status"] == "Blocked"]
            elif only == "nofile":
                g["items"] = [i for i in g["items"] if not atts.get(i["id"])]
    people = c.execute("SELECT id, name, org FROM people WHERE active=1 ORDER BY name").fetchall()
    avls = c.execute("SELECT id, name FROM avls WHERE active=1 ORDER BY name").fetchall()
    c.close()
    return templates.TemplateResponse(request, "ie_report.html", {"user": user, "r": r,
        "groups": groups, "totals": totals, "atts": atts, "people": people, "avls": avls,
        "item_statuses": db.IE_ITEM_STATUSES, "priorities": db.IE_PRIORITIES,
        "report_statuses": db.IE_REPORT_STATUSES, "reviewers": db.IE_REVIEWERS, "only": only})

@app.post("/ie/report/{rid}/save")
def ie_report_save(rid: int, request: Request, name: str = Form(...), reviewer: str = Form("DNV"),
                   status: str = Form("Planning"), kickoff_date: str = Form(""),
                   target_date: str = Form(""), shared_with: str = Form(""),
                   notes: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    c.execute("UPDATE ie_reports SET name=?, reviewer=?, status=?, kickoff_date=?, target_date=?, "
              "shared_with=?, notes=? WHERE id=?",
              (name.strip(), reviewer, status, kickoff_date, target_date,
               shared_with.strip(), notes.strip(), rid))
    c.commit(); c.close()
    db.log(user["email"], "ie:report:save", f"{name.strip()} -> {status}")
    return RedirectResponse(f"/ie/report/{rid}", status_code=303)

@app.post("/ie/report/{rid}/delete")
def ie_report_delete(rid: int, request: Request, user=Depends(require_admin)):
    c = db.conn()
    row = c.execute("SELECT name FROM ie_reports WHERE id=?", (rid,)).fetchone()
    c.execute("UPDATE ie_reports SET active=0 WHERE id=?", (rid,))
    c.commit(); c.close()
    if row:
        db.log(user["email"], "ie:report:delete", row["name"])
    return RedirectResponse("/ie", status_code=303)

@app.post("/ie/item/{iid}/save")
def ie_item_save(iid: int, request: Request, status: str = Form(...),
                 owner_person_id: str = Form(""), owner_other: str = Form(""),
                 due_date: str = Form(""), priority: str = Form("Normal"),
                 gap: str = Form(""), notes: str = Form(""), user=Depends(require_editor)):
    if status not in db.IE_ITEM_STATUSES:
        status = "Not Started"
    if priority not in db.IE_PRIORITIES:
        priority = "Normal"
    c = db.conn()
    row = c.execute("SELECT report_id, review_item, owner FROM ie_report_items WHERE id=?",
                    (iid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/ie", status_code=303)
    oid = int(owner_person_id) if owner_person_id.strip().isdigit() and int(owner_person_id) > 0 else None
    oname = ""
    if oid:
        p = c.execute("SELECT name FROM people WHERE id=? AND active=1", (oid,)).fetchone()
        oname, oid = (p["name"], oid) if p else ("", None)
    owner_txt = oname or owner_other.strip() or (row["owner"] if not oid else "")
    c.execute("UPDATE ie_report_items SET status=?, owner=?, owner_person_id=?, due_date=?, "
              "priority=?, gap=?, notes=?, updated_by=?, updated_at=? WHERE id=?",
              (status, owner_txt, oid, due_date, priority, gap.strip(), notes.strip(),
               user["email"], now(), iid))
    c.commit(); c.close()
    db.log(user["email"], "ie:item", f"{row['review_item'][:60]} -> {status}")
    return RedirectResponse(f"/ie/report/{row['report_id']}", status_code=303)

@app.post("/ie/report/{rid}/section/{sid}/save")
def ie_section_save(rid: int, sid: int, request: Request, owner_person_id: str = Form(""),
                    owner_other: str = Form(""), user=Depends(require_editor)):
    c = db.conn()
    oid = int(owner_person_id) if owner_person_id.strip().isdigit() and int(owner_person_id) > 0 else None
    oname = ""
    if oid:
        p = c.execute("SELECT name FROM people WHERE id=? AND active=1", (oid,)).fetchone()
        oname, oid = (p["name"], oid) if p else ("", None)
    c.execute("UPDATE ie_report_sections SET owner=?, owner_person_id=? WHERE id=? AND report_id=?",
              (oname or owner_other.strip(), oid, sid, rid))
    c.commit(); c.close()
    return RedirectResponse(f"/ie/report/{rid}", status_code=303)

@app.post("/ie/report/{rid}/item/add")
def ie_item_add(rid: int, request: Request, section_id: int = Form(...),
                review_item: str = Form(...), sub_section: str = Form(""),
                item_id: str = Form(""), evidence: str = Form(""),
                priority: str = Form("Normal"), user=Depends(require_editor)):
    ri = review_item.strip()
    if priority not in db.IE_PRIORITIES:
        priority = "Normal"
    if ri:
        c = db.conn()
        nxt = c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM ie_report_items "
                        "WHERE report_id=? AND section_id=?", (rid, section_id)).fetchone()[0]
        c.execute("INSERT INTO ie_report_items(report_id, section_id, item_id, sub_section, "
                  "review_item, evidence, priority, sort_order, updated_by, updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (rid, section_id, item_id.strip(), sub_section.strip(), ri, evidence.strip(),
                   priority, nxt, user["email"], now()))
        c.commit(); c.close()
        db.log(user["email"], "ie:item:add", ri[:60])
    return RedirectResponse(f"/ie/report/{rid}", status_code=303)

@app.post("/ie/item/{iid}/delete")
def ie_item_delete(iid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT report_id, review_item FROM ie_report_items WHERE id=?", (iid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/ie", status_code=303)
    n = c.execute(f"SELECT COUNT(*) FROM attachments WHERE kind='{IE_KIND}' AND ref_id=?",
                  (iid,)).fetchone()[0]
    if n:
        c.close()
        return RedirectResponse(f"/ie/report/{row['report_id']}?err=files", status_code=303)
    c.execute("DELETE FROM ie_report_items WHERE id=?", (iid,))
    c.commit(); c.close()
    db.log(user["email"], "ie:item:delete", row["review_item"][:60])
    return RedirectResponse(f"/ie/report/{row['report_id']}", status_code=303)

# ---------------- 12b) IE template management ----------------
@app.get("/ie/templates", response_class=HTMLResponse)
def ie_templates(request: Request, t: int = 0, user=Depends(require_user)):
    c = db.conn()
    tmpls = c.execute("SELECT t.*, "
                      "(SELECT COUNT(*) FROM ie_template_sections s WHERE s.template_id=t.id) AS n_sec, "
                      "(SELECT COUNT(*) FROM ie_template_items i JOIN ie_template_sections s "
                      " ON s.id=i.section_id WHERE s.template_id=t.id) AS n_items "
                      "FROM ie_templates t ORDER BY t.active DESC, t.name").fetchall()
    sel = t or (tmpls[0]["id"] if tmpls else 0)
    cur = c.execute("SELECT * FROM ie_templates WHERE id=?", (sel,)).fetchone()
    sections = []
    if cur:
        for s in c.execute("SELECT * FROM ie_template_sections WHERE template_id=? "
                           "ORDER BY sort_order, id", (sel,)):
            items = c.execute("SELECT * FROM ie_template_items WHERE section_id=? "
                              "ORDER BY sort_order, id", (s["id"],)).fetchall()
            sections.append({"sec": s, "items": items})
    history = c.execute("SELECT * FROM ie_template_revisions WHERE template_id=? "
                        "ORDER BY id DESC LIMIT 15", (sel,)).fetchall() if cur else []
    usage = c.execute("SELECT r.id, r.name, p.name AS product FROM ie_reports r "
                      "JOIN products p ON p.id=r.product_id WHERE r.template_id=? AND r.active=1",
                      (sel,)).fetchall() if cur else []
    c.close()
    return templates.TemplateResponse(request, "ie_templates.html", {"user": user, "tmpls": tmpls,
        "cur": cur, "sections": sections, "history": history, "usage": usage,
        "categories": db.CATEGORIES, "reviewers": db.IE_REVIEWERS, "priorities": db.IE_PRIORITIES})

@app.post("/ie/templates/add")
def ie_tmpl_add(request: Request, name: str = Form(...), reviewer: str = Form("DNV"),
                category: str = Form(""), notes: str = Form(""), source_url: str = Form(""),
                copy_from: str = Form(""), user=Depends(require_editor)):
    nm = name.strip()
    if not nm:
        return RedirectResponse("/ie/templates", status_code=303)
    c = db.conn()
    if c.execute("SELECT 1 FROM ie_templates WHERE name=?", (nm,)).fetchone():
        c.close()
        return RedirectResponse("/ie/templates?err=dup", status_code=303)
    c.execute("INSERT INTO ie_templates(name, reviewer, category, notes, source_url, "
              "created_by, created_at) VALUES(?,?,?,?,?,?,?)",
              (nm, reviewer, category if category in db.CATEGORIES else "", notes.strip(),
               source_url.strip(), user["email"], now()))
    tid = c.execute("SELECT id FROM ie_templates WHERE name=?", (nm,)).fetchone()["id"]
    if copy_from.strip().isdigit():
        for s in c.execute("SELECT * FROM ie_template_sections WHERE template_id=? "
                           "ORDER BY sort_order, id", (int(copy_from),)).fetchall():
            c.execute("INSERT INTO ie_template_sections(template_id, code, title, owner, sort_order) "
                      "VALUES(?,?,?,?,?)", (tid, s["code"], s["title"], s["owner"], s["sort_order"]))
            nsid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            c.execute("INSERT INTO ie_template_items(section_id, item_id, sub_section, review_item, "
                      "evidence, suggested_owner, priority, source, sort_order) "
                      "SELECT ?, item_id, sub_section, review_item, evidence, suggested_owner, "
                      "priority, source, sort_order FROM ie_template_items WHERE section_id=?",
                      (nsid, s["id"]))
    c.commit(); c.close()
    db.log(user["email"], "ie:template:add", nm)
    return RedirectResponse(f"/ie/templates?t={tid}", status_code=303)

@app.post("/ie/templates/{tid}/edit")
def ie_tmpl_edit(tid: int, request: Request, name: str = Form(...), reviewer: str = Form("DNV"),
                 category: str = Form(""), notes: str = Form(""), source_url: str = Form(""),
                 user=Depends(require_editor)):
    nm = name.strip()
    if not nm:
        return RedirectResponse(f"/ie/templates?t={tid}", status_code=303)
    c = db.conn()
    if c.execute("SELECT 1 FROM ie_templates WHERE name=? AND id<>?", (nm, tid)).fetchone():
        c.close()
        return RedirectResponse(f"/ie/templates?t={tid}&err=dup", status_code=303)
    db.ie_record_revision(c, tid, "scope", f"renamed/rescoped to '{nm}'", user["email"])
    c.execute("UPDATE ie_templates SET name=?, reviewer=?, category=?, notes=?, source_url=? "
              "WHERE id=?", (nm, reviewer, category if category in db.CATEGORIES else "",
                             notes.strip(), source_url.strip(), tid))
    c.commit(); c.close()
    db.log(user["email"], "ie:template:edit", nm)
    return RedirectResponse(f"/ie/templates?t={tid}", status_code=303)

@app.post("/ie/templates/{tid}/toggle")
def ie_tmpl_toggle(tid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    db.ie_record_revision(c, tid, "retire/restore", "", user["email"])
    c.execute("UPDATE ie_templates SET active = 1 - active WHERE id=?", (tid,))
    c.commit(); c.close()
    return RedirectResponse(f"/ie/templates?t={tid}", status_code=303)

@app.post("/ie/templates/{tid}/section/add")
def ie_sec_add(tid: int, request: Request, title: str = Form(...), code: str = Form(""),
               owner: str = Form(""), user=Depends(require_editor)):
    ti = title.strip()
    if ti:
        c = db.conn()
        db.ie_record_revision(c, tid, "add section", ti, user["email"])
        nxt = c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM ie_template_sections "
                        "WHERE template_id=?", (tid,)).fetchone()[0]
        c.execute("INSERT INTO ie_template_sections(template_id, code, title, owner, sort_order) "
                  "VALUES(?,?,?,?,?)", (tid, code.strip(), ti, owner.strip(), nxt))
        c.commit(); c.close()
        db.log(user["email"], "ie:section:add", ti)
    return RedirectResponse(f"/ie/templates?t={tid}", status_code=303)

@app.post("/ie/templates/section/{sid}/save")
def ie_sec_save(sid: int, request: Request, title: str = Form(...), code: str = Form(""),
                owner: str = Form(""), sort_order: int = Form(0), user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT template_id, title FROM ie_template_sections WHERE id=?", (sid,)).fetchone()
    if not row or not title.strip():
        c.close()
        return RedirectResponse("/ie/templates", status_code=303)
    db.ie_record_revision(c, row["template_id"], "edit section", row["title"], user["email"])
    c.execute("UPDATE ie_template_sections SET title=?, code=?, owner=?, sort_order=? WHERE id=?",
              (title.strip(), code.strip(), owner.strip(), sort_order, sid))
    c.commit(); c.close()
    return RedirectResponse(f"/ie/templates?t={row['template_id']}", status_code=303)

@app.post("/ie/templates/section/{sid}/delete")
def ie_sec_delete(sid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT template_id, title FROM ie_template_sections WHERE id=?", (sid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/ie/templates", status_code=303)
    db.ie_record_revision(c, row["template_id"], "delete section", row["title"], user["email"])
    c.execute("DELETE FROM ie_template_sections WHERE id=?", (sid,))
    c.commit(); c.close()
    db.log(user["email"], "ie:section:delete", row["title"])
    return RedirectResponse(f"/ie/templates?t={row['template_id']}", status_code=303)

@app.post("/ie/templates/section/{sid}/item/add")
def ie_tmpl_item_add(sid: int, request: Request, review_item: str = Form(...),
                     item_id: str = Form(""), sub_section: str = Form(""),
                     evidence: str = Form(""), suggested_owner: str = Form(""),
                     priority: str = Form("Normal"), source: str = Form(""),
                     user=Depends(require_editor)):
    ri = review_item.strip()
    c = db.conn()
    row = c.execute("SELECT template_id FROM ie_template_sections WHERE id=?", (sid,)).fetchone()
    if not row or not ri:
        c.close()
        return RedirectResponse("/ie/templates", status_code=303)
    db.ie_record_revision(c, row["template_id"], "add item", ri, user["email"])
    nxt = c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM ie_template_items "
                    "WHERE section_id=?", (sid,)).fetchone()[0]
    c.execute("INSERT INTO ie_template_items(section_id, item_id, sub_section, review_item, "
              "evidence, suggested_owner, priority, source, sort_order) VALUES(?,?,?,?,?,?,?,?,?)",
              (sid, item_id.strip(), sub_section.strip(), ri, evidence.strip(),
               suggested_owner.strip(),
               priority if priority in db.IE_PRIORITIES else "Normal", source.strip(), nxt))
    c.commit(); c.close()
    db.log(user["email"], "ie:template:item:add", ri[:60])
    return RedirectResponse(f"/ie/templates?t={row['template_id']}", status_code=303)

@app.post("/ie/templates/item/{iid}/save")
def ie_tmpl_item_save(iid: int, request: Request, review_item: str = Form(...),
                      item_id: str = Form(""), sub_section: str = Form(""),
                      evidence: str = Form(""), suggested_owner: str = Form(""),
                      priority: str = Form("Normal"), sort_order: int = Form(0),
                      user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT i.review_item, s.template_id FROM ie_template_items i "
                    "JOIN ie_template_sections s ON s.id=i.section_id WHERE i.id=?", (iid,)).fetchone()
    if not row or not review_item.strip():
        c.close()
        return RedirectResponse("/ie/templates", status_code=303)
    db.ie_record_revision(c, row["template_id"], "edit item", row["review_item"], user["email"])
    c.execute("UPDATE ie_template_items SET review_item=?, item_id=?, sub_section=?, evidence=?, "
              "suggested_owner=?, priority=?, sort_order=? WHERE id=?",
              (review_item.strip(), item_id.strip(), sub_section.strip(), evidence.strip(),
               suggested_owner.strip(),
               priority if priority in db.IE_PRIORITIES else "Normal", sort_order, iid))
    c.commit(); c.close()
    return RedirectResponse(f"/ie/templates?t={row['template_id']}", status_code=303)

@app.post("/ie/templates/item/{iid}/delete")
def ie_tmpl_item_delete(iid: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    row = c.execute("SELECT i.review_item, s.template_id FROM ie_template_items i "
                    "JOIN ie_template_sections s ON s.id=i.section_id WHERE i.id=?", (iid,)).fetchone()
    if not row:
        c.close()
        return RedirectResponse("/ie/templates", status_code=303)
    db.ie_record_revision(c, row["template_id"], "delete item", row["review_item"], user["email"])
    c.execute("DELETE FROM ie_template_items WHERE id=?", (iid,))
    c.commit(); c.close()
    return RedirectResponse(f"/ie/templates?t={row['template_id']}", status_code=303)

@app.post("/ie/templates/undo/{rev_id}")
def ie_tmpl_undo(rev_id: int, request: Request, user=Depends(require_editor)):
    c = db.conn()
    res = db.ie_restore_revision(c, rev_id, user["email"])
    if not res:
        c.close()
        return RedirectResponse("/ie/templates?err=gone", status_code=303)
    tid, action = res
    c.commit(); c.close()
    db.log(user["email"], "ie:template:undo", f"t{tid}: reverted '{action}'")
    return RedirectResponse(f"/ie/templates?t={tid}&undone={action}", status_code=303)

@app.get("/ie/report/{rid}/bundle.zip")
def ie_bundle(rid: int, request: Request, user=Depends(require_user)):
    """The IE evidence pack: files foldered by section, with manifest and summary."""
    c = db.conn()
    r = c.execute("SELECT r.*, p.name AS product FROM ie_reports r JOIN products p ON p.id=r.product_id "
                  "WHERE r.id=?", (rid,)).fetchone()
    if not r:
        c.close()
        return RedirectResponse("/ie", status_code=303)
    groups, totals, atts = _ie_progress(c, rid)
    c.close()
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    base = f"{_safe(r['reviewer'], 20)}_{_safe(r['product'], 40)}_IE_{stamp}"
    path = os.path.join(PKG_DIR, base + ".zip")
    man, summ = [], []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for gi, g in enumerate(groups, 1):
            folder = f"{gi:02d}_{_safe(g['sec']['title'], 50)}"
            for it in g["items"]:
                files = atts.get(it["id"], [])
                summ.append([g["sec"]["title"], it["item_id"], it["sub_section"],
                             it["review_item"], it["evidence"], it["priority"], it["status"],
                             it["owner"], it["due_date"], len(files),
                             "INCLUDED" if files else "NO EVIDENCE", it["gap"]])
                for f in files:
                    arc = f"{folder}/{_safe(it['item_id'] or it['sub_section'], 40)}/{_safe(f['filename'], 90)}"
                    if os.path.exists(f["stored_path"]):
                        z.write(f["stored_path"], arc)
                        man.append([g["sec"]["title"], it["item_id"], it["review_item"], arc])
                    else:
                        man.append([g["sec"]["title"], it["item_id"], it["review_item"],
                                    "FILE NOT FOUND ON DISK"])

        def csv_bytes(header, rows):
            buf = io.StringIO(); w = csv.writer(buf); w.writerow(header)
            for row in rows:
                w.writerow(row)
            return buf.getvalue()

        z.writestr("MANIFEST.csv", csv_bytes(
            ["Section", "Item ID", "Review item", "Path in zip"], man))
        z.writestr("IE_SUMMARY.csv", csv_bytes(
            ["Section", "Item ID", "Sub-section", "Preparation item / review question",
             "Required evidence", "Priority", "Status", "Owner", "Due", "Files", "Result",
             "Gap / action"], summ))
        L = ["IE TECHNOLOGY REVIEW - EVIDENCE SUMMARY", "=" * 62,
             f"Product      : {r['product']}",
             f"Report       : {r['name']}",
             f"Reviewer     : {r['reviewer']}",
             f"Status       : {r['status']}",
             f"Kickoff      : {r['kickoff_date'] or '-'}    Target: {r['target_date'] or '-'}",
             f"Built        : {now()} by {user['email']}", ""]
        if r["shared_with"]:
            L += [f"Shared with  : {r['shared_with']}", ""]
        L += [f"{totals['done']}/{totals['n']} items accepted ({totals['pct']}%), "
              f"{totals['wip']} in progress, {totals['blocked']} blocked, "
              f"{totals['crit_open']} Critical still open.",
              f"{totals['files']} evidence file(s) attached.", "",
              "BY SECTION", "-" * 62,
              f"{'Section':<44}{'Items':>6}{'Done':>6}{'Files':>6}"]
        for g in groups:
            L.append(f"{g['sec']['title'][:43]:<44}{g['n']:>6}{g['done']:>6}{g['files']:>6}")
        L += [f"{'TOTAL':<44}{totals['n']:>6}{totals['done']:>6}{totals['files']:>6}", "",
              "DETAIL", "-" * 62]
        for gi, g in enumerate(groups, 1):
            L.append(f"{gi:02d}. {g['sec']['title']}  ({g['done']}/{g['n']}, owner: {g['sec']['owner'] or '-'})")
            for it in g["items"]:
                files = atts.get(it["id"], [])
                mark = "[x]" if files else "[ ]"
                L.append(f"    {mark} {it['item_id']:<6} ({it['priority']}, {it['status']}) {it['review_item']}")
                if it["evidence"]:
                    L.append(f"           evidence: {it['evidence']}")
                for f in files:
                    L.append(f"           - {f['filename']}")
                if it["gap"]:
                    L.append(f"           GAP: {it['gap']}")
            L.append("")
        z.writestr("IE_SUMMARY.txt", "\n".join(L))
    db.log(user["email"], "ie:bundle", f"{r['name']} - {totals['files']} files")
    return FileResponse(path, filename=base + ".zip", media_type="application/zip")
