# Qcells AVL Manager

Multi-user dashboard to track Qcells products across TPO AVLs: update listing
statuses cell-by-cell, add/remove products and AVL accounts (soft delete),
assign the trifecta (Account Manager + Sr. Commercial Rep per AVL,
Product/Technical reps per product), with a full audit trail.
Seeded with the Aug-2026 AVL Status matrix.

## Run locally (WSL Ubuntu)
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env            # edit SECRET_KEY
    export $(grep -v '^#' .env | xargs)
    uvicorn app.main:app --reload --port 8000
Open http://localhost:8000 - dev mode sign-in (any name + @qcells.com email,
no password; for local testing only).

## Real @qcells.com login
Option A (recommended if hosting on Azure): deploy to Azure App Service,
turn on built-in Authentication with Microsoft Entra ID restricted to the
Qcells tenant, set AUTH_MODE=easyauth. Zero auth code to maintain.

Option B (any host): register an app in Entra ID, set redirect URI to
https://<your-host>/auth/callback, fill the OIDC_* vars in .env, set
AUTH_MODE=oidc. The app additionally enforces the @qcells.com domain
server-side whichever provider is used.

## Data
SQLite file avl.db (auto-created + seeded on first run). Set AVL_DB to move
it. Statuses mirror the AVL Strategy legend: Listed, In Review, Execution,
Engagement, Opportunity, No Interest, No Info, N/A, plus Pre-launch.

## v6 features
Per-cell notes (pencil icon on the matrix), CSV exports (Dashboard/History/Calls),
Action items with overdue tracking (/actions), one-click PPTX status snapshot
(/export/status.pptx), dataroom checklists per product x TPO (/dataroom, seeded
from the G4-ESS tracker workstreams), weekly digest preview (/digest) +
scripts/send_digest.py for cron email, roles (viewer/editor/admin; first user is
admin; manage at /admin), DB backup button + scripts/backup.sh nightly cron,
and attachments (/files) for certs, datasheets and TPO docs.
