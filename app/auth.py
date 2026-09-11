"""Auth for Qcells AVL Manager.

Modes, chosen by AUTH_MODE env var:
  dev    - local login form; any name + email is accepted but the email domain
           is still enforced (ALLOWED_DOMAIN). Use this in WSL while developing.
           Never expose this beyond your own machine.
  shared - the dev form plus one team-wide password (SHARED_PASSWORD). A stopgap
           for a hosted trial when an SSO app registration is not available yet:
           it is not per-person auth and gives no accountability beyond the email
           someone types, but it is the difference between "the team can use it"
           and "anyone with the URL can". Move to oidc as soon as you can.
  oidc   - real SSO via any OIDC provider (Microsoft Entra ID recommended for
           @qcells.com). Configure OIDC_* env vars; the id_token email domain
           is enforced server-side regardless of provider settings.

Deployment shortcut: if you host on Azure App Service, its built-in
authentication ("Easy Auth") can front the whole app with Entra ID and you
can run AUTH_MODE=easyauth to trust the X-MS-CLIENT-PRINCIPAL-NAME header.
"""
import os, base64, json, hmac, time, hashlib, secrets, datetime
from fastapi import Request, HTTPException
from starlette.responses import RedirectResponse

ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "qcells.com")
AUTH_MODE = os.environ.get("AUTH_MODE", "dev")
SHARED_PASSWORD = os.environ.get("SHARED_PASSWORD", "")
MIN_SHARED_PASSWORD = 12

def shared_password_configured():
    """Fail closed: a short or missing password is treated as not configured."""
    return len(SHARED_PASSWORD) >= MIN_SHARED_PASSWORD

def shared_password_ok(supplied):
    if not shared_password_configured():
        return False
    return hmac.compare_digest(supplied or "", SHARED_PASSWORD)

# With an allowlist on, knowing the team password is not enough: the address must
# already be on the roster. That is what makes removing someone mean anything.
REQUIRE_KNOWN_USER = os.environ.get("REQUIRE_KNOWN_USER", "") == "1"

def user_known(email):
    """True if this address may sign in. Open until the first user exists, so the
    allowlist can never lock everyone out of a fresh deployment."""
    if not REQUIRE_KNOWN_USER:
        return True
    if (email or "").lower() in ADMIN_EMAILS:
        return True
    from . import db
    c = db.conn()
    row = c.execute("SELECT (SELECT COUNT(*) FROM users) n, "
                    "(SELECT COUNT(*) FROM users WHERE lower(email)=lower(?)) hit",
                    (email,)).fetchone()
    c.close()
    return row["n"] == 0 or row["hit"] > 0

# A long shared token so a scheduler elsewhere can pull a backup without a
# session. Short or unset means the route does not exist.
BACKUP_TOKEN = os.environ.get("BACKUP_TOKEN", "")
MIN_BACKUP_TOKEN = 24

def backup_token_ok(supplied):
    if len(BACKUP_TOKEN) < MIN_BACKUP_TOKEN:
        return False
    return hmac.compare_digest(supplied or "", BACKUP_TOKEN)

def form_login_enabled():
    return AUTH_MODE in ("dev", "shared", "local")

def personal_passwords_enabled():
    """Whether an account can have a password of its own.

    True for shared as well as local, because the two differ only in whether a
    team password exists at all - both prefer an account's own password when it
    has one. That means nobody has to reconfigure anything for one person to
    move over, and local is simply where you end up once the team password is
    gone.
    """
    return AUTH_MODE in ("shared", "local")


# ---- per-person passwords (AUTH_MODE=local) --------------------------------
# scrypt from the standard library: memory-hard, so a stolen database cannot be
# attacked at the speed a plain hash allows, and no new dependency to keep
# patched. The parameters are recorded next to each hash rather than assumed, so
# they can be raised later without invalidating everyone's password.
_PW_N, _PW_R, _PW_P, _PW_DKLEN = 2 ** 14, 8, 1, 32
PW_ALGO = f"scrypt-{_PW_N}-{_PW_R}-{_PW_P}"
MIN_PASSWORD = 12

def hash_password(password, salt=None):
    """Returns (algo, salt_hex, hash_hex). A fresh random salt unless one is given."""
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt((password or "").encode("utf-8"), salt=salt, n=_PW_N, r=_PW_R,
                        p=_PW_P, dklen=_PW_DKLEN, maxmem=_PW_N * _PW_R * 256)
    return PW_ALGO, salt.hex(), dk.hex()

def verify_password(password, algo, salt_hex, hash_hex):
    """Constant-time check against a stored hash, using that hash's own parameters."""
    if not (algo and salt_hex and hash_hex):
        return False
    try:
        kind, n, r, p = algo.split("-")
        if kind != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        dk = hashlib.scrypt((password or "").encode("utf-8"), salt=bytes.fromhex(salt_hex),
                            n=n, r=r, p=p, dklen=len(hash_hex) // 2, maxmem=n * r * 256)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)

def password_problem(password, email=""):
    """The rule worth enforcing is length. Returns a message, or None if it will do.

    Deliberately not a checklist of character classes: they push people towards
    predictable substitutions without buying much, and a long passphrase beats a
    short scramble.
    """
    pw = password or ""
    if len(pw) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if email and pw.strip().lower() == email.strip().lower():
        return "That is your email address."
    return None

def temp_password():
    """A one-time password for an admin to hand over, changed on first sign-in."""
    return secrets.token_urlsafe(12)

# Per-account lockout, on top of the per-IP one. Without it, one account can be
# attacked from many addresses and never trip the address counter.
ACCOUNT_LOCK_AFTER = 8
ACCOUNT_LOCK_MINUTES = 15

def account_locked_until(row):
    """The lock expiry if this account is currently locked out, else None."""
    if not row:
        return None
    until = (row["locked_until"] or "") if "locked_until" in row.keys() else ""
    if until and until > datetime.datetime.now().isoformat(timespec="seconds"):
        return until
    return None

def startup_warnings():
    """Configuration that is legitimate locally but dangerous once hosted."""
    out = []
    behind_tls = os.environ.get("SECURE_COOKIES", "") == "1"
    if AUTH_MODE == "dev" and behind_tls:
        out.append("AUTH_MODE=dev behind TLS: anyone who reaches this URL can sign "
                   "in with any @%s address and no password. Set AUTH_MODE=oidc, or "
                   "AUTH_MODE=shared with SHARED_PASSWORD as a stopgap." % ALLOWED_DOMAIN)
    if REQUIRE_KNOWN_USER and AUTH_MODE == "easyauth":
        out.append("REQUIRE_KNOWN_USER has no effect in easyauth mode; the platform "
                   "decides who reaches the app.")
    if AUTH_MODE == "shared" and not shared_password_configured():
        out.append("AUTH_MODE=shared but SHARED_PASSWORD is missing or shorter than "
                   "%d characters. All logins will be refused until it is set."
                   % MIN_SHARED_PASSWORD)
    if AUTH_MODE == "local" and not shared_password_configured():
        out.append("AUTH_MODE=local with no SHARED_PASSWORD: anyone who has not set "
                   "a password of their own cannot sign in until an admin issues "
                   "them a temporary one from the Admin page.")
    if os.environ.get("SECRET_KEY", "change-me-in-prod") == "change-me-in-prod" and behind_tls:
        out.append("SECRET_KEY is still the default while hosted: sessions are forgeable.")
    return out

# Failed form logins, per client address. In-memory is the right scope here: the
# app runs as a single process, and a restart clearing the counters is not a
# meaningful weakening of a stopgap.
#
# This counter and the per-account one do different jobs, so they are set
# differently. The account counter (8) stops someone guessing at one known
# address. This one stops a spray across many accounts - and has to allow for a
# whole office arriving from a single NAT address, where a handful of ordinary
# typos in fifteen minutes would otherwise lock out everybody at once.
_FAILS = {}
LOCKOUT_AFTER = 20
LOCKOUT_WINDOW = 900      # 15 minutes

def login_blocked(ip):
    hits = [t for t in _FAILS.get(ip, []) if time.time() - t < LOCKOUT_WINDOW]
    _FAILS[ip] = hits
    return len(hits) >= LOCKOUT_AFTER

def note_login_failure(ip):
    _FAILS.setdefault(ip, []).append(time.time())

def clear_login_failures(ip):
    _FAILS.pop(ip, None)

def domain_ok(email: str) -> bool:
    return email.lower().strip().endswith("@" + ALLOWED_DOMAIN)

def current_user(request: Request):
    if AUTH_MODE == "easyauth":
        principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if principal and domain_ok(principal):
            return {"email": principal, "name": principal.split("@")[0]}
        return None
    return request.session.get("user")

# Reachable while somebody is being made to set a password, or the redirect has
# nowhere to land and the app becomes unusable instead of merely insistent.
_PW_EXEMPT = ("/account/password", "/logout", "/login", "/static", "/healthz")

def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    user = dict(user)
    try:
        user["role"] = get_role(user["email"])
    except Exception:
        user["role"] = "editor"
    # The only thing that forces a change is a temporary password an admin
    # issued and therefore knows. Signing in on the team password does not: people
    # move to their own when they choose to. Read from the database rather than
    # trusted from the session, so a reset takes hold of a session that is
    # already open instead of waiting for that person to sign out.
    if personal_passwords_enabled():
        try:
            from . import db
            c = db.conn()
            row = c.execute("SELECT pw_hash, must_change FROM users WHERE lower(email)=lower(?)",
                            (user["email"],)).fetchone()
            c.close()
            user["must_change"] = bool(row) and bool(row["must_change"])
            user["own_password"] = bool(row) and bool(row["pw_hash"])
        except Exception:
            pass          # a lookup failure must not lock everybody out
    if user.get("must_change") and not request.url.path.startswith(_PW_EXEMPT):
        raise HTTPException(status_code=307, headers={"Location": "/account/password"})
    return user

# ---- OIDC (Entra ID / Google) ----
def oauth_client():
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="sso",
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
        server_metadata_url=os.environ["OIDC_METADATA_URL"],
        # Entra ID example metadata URL:
        # https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth.sso


# ---- roles: viewer / editor / admin ----
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

def get_role(email: str) -> str:
    from . import db
    c = db.conn()
    row = c.execute("SELECT role, (SELECT COUNT(*) FROM users) AS n FROM users WHERE email=?",
                    (email,)).fetchone()
    c.close()
    if email.lower() in ADMIN_EMAILS:
        return "admin"
    return row["role"] if row else "editor"

def require_editor(request: Request):
    user = require_user(request)
    role = get_role(user["email"])
    if role == "viewer":
        raise HTTPException(status_code=403, detail="Read-only account: ask an admin for editor access.")
    user = dict(user); user["role"] = role
    return user

def require_admin(request: Request):
    user = require_user(request)
    if get_role(user["email"]) != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    return user
