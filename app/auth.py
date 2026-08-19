"""Auth for Qcells AVL Manager.

Two modes, chosen by AUTH_MODE env var:
  dev  - local login form; any name + email is accepted but the email domain
         is still enforced (ALLOWED_DOMAIN). Use this in WSL while developing.
  oidc - real SSO via any OIDC provider (Microsoft Entra ID recommended for
         @qcells.com). Configure OIDC_* env vars; the id_token email domain
         is enforced server-side regardless of provider settings.

Deployment shortcut: if you host on Azure App Service, its built-in
authentication ("Easy Auth") can front the whole app with Entra ID and you
can run AUTH_MODE=easyauth to trust the X-MS-CLIENT-PRINCIPAL-NAME header.
"""
import os, base64, json
from fastapi import Request, HTTPException
from starlette.responses import RedirectResponse

ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "qcells.com")
AUTH_MODE = os.environ.get("AUTH_MODE", "dev")

def domain_ok(email: str) -> bool:
    return email.lower().strip().endswith("@" + ALLOWED_DOMAIN)

def current_user(request: Request):
    if AUTH_MODE == "easyauth":
        principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if principal and domain_ok(principal):
            return {"email": principal, "name": principal.split("@")[0]}
        return None
    return request.session.get("user")

def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    user = dict(user)
    try:
        user["role"] = get_role(user["email"])
    except Exception:
        user["role"] = "editor"
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
