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

## v7 features
Workstream template library (/workstreams): reusable due-diligence requirement lists
scoped by product type (DC Module, AC Module, MLPE, Inverter, ESS, Smart Panel, Other) and
optionally to a single TPO. Ships starter sets for each type; the old G4-ESS list is
now just the ESS-scoped template. The Dataroom picker offers the best-matching
templates first (category+AVL, then category, then AVL, then generic) and applies them
in Merge (add missing only) or Replace (re-seed rows nobody has touched) mode. Ad-hoc
per-TPO requirements can be added straight onto a checklist.

Attachments can now be filed against a specific workstream requirement
(AVL x product x requirement), not just a product/AVL/call. Upload inline from the
Dataroom row, or from /files via an AVL -> product -> requirement picker. Existing
files can be re-filed onto a different requirement or scope with the Move control, and
deleted. Removing a requirement that still holds files is blocked so nothing is orphaned.

## v8 - requirement library imported from the EnFin AVL trackers
Templates now mirror the EnFin AVL Requirements Tracker sheets: each row is a
Document Category + Required Document + obligation (Required / Conditional /
Optional) + notes, so a checklist reads the same as the sheet it came from.
Seeded from the Jun-2026 sheets (source URL kept on each template):

  PV Module (DC)              84 requirements / 14 categories
  AC Module (P-PERC)          78 / 11
  AC Module (N-TOPCon)        78 / 11
  Inverter                    88 / 13
  Microinverter / MLPE        88 / 13
  ESS / BESS (Gen4)           65 / 10
  Smart Panel                 94 / 13

The Dataroom groups a checklist by Document Category with a "required complete"
rollup per group and overall, and filters by obligation or "still open". Files
attach to a specific requirement and are labelled AVL / product / category /
requirement. Adding "Smart Panel" as a product type; re-running startup migrates
existing checklists (new doc_category and obligation columns default safely).

## v9 - people come from the Team roster
The Manage page no longer accepts typed-in names. Account Manager, Sr. Commercial
Rep and Product/Technical reps are picked from the roster managed on /team, and
saving a seat writes a dated assignment, so Team keeps the history of who covered
what and when. Assignments are the single source of truth; the name columns on
products/avls are refreshed from them as a cache for the dashboard and exports.

The roster on /team gains edit and retire: retiring someone ends their live
assignments, leaves those seats vacant and drops them from every picker, while
their history stays. Re-adding a retired name restores that person instead of
creating a duplicate. A person's Org decides which pickers they appear in --
Sales for AM / Sr. Commercial Rep, Products / CE for Product/Technical Rep,
Other for both. Names typed in before this change are adopted into the roster
automatically on first start.

## v10 - AVL Contacts
/contacts is the TPO-side address book: for each AVL, who our point of contact is
(name, role/title, email, phone, website, notes). Distinct from the Qcells roster
on /team, which is who covers the account from our side.

One contact per AVL can be starred as the primary point of contact. Roles are
suggested from a list but stay free text, since every financier titles these
differently. Bare domains are stored as https:// URLs and emails are lowercased.
Remove is a soft delete so someone who leaves the TPO stops appearing but is still
readable via "show former contacts"; removing a contact also clears their POC star.
Filter by AVL, search name / role / email, and export the live contacts to CSV
at /contacts.csv.

## v11 - status tracker + submission packages
The Dataroom page opens with a status tracker: one row per document category
showing required-done with a progress bar, in-progress / blocked / not-started
counts, files attached, and "Required w/o file" - the count that will show as a
gap in a submission. Category names link down to their section. The tracker always
covers the whole checklist even when the list below is filtered.

/dataroom/package (also linked from the tracker) builds the submission itself:
choose product x TPO and a scope (all / Required only / Required + Conditional),
preview exactly what will be sent with gaps highlighted, then build a ZIP
containing the attached files foldered by document category plus:
  MANIFEST.csv   every in-scope requirement, its obligation and status, the file
                 path in the package, and "MISSING - no file attached" for gaps
  CONTENTS.txt   readable index with [x] / [ ] MISSING per requirement
Built packages are kept, so each one can be re-downloaded and its manifest read
back as a record of what was sent when and by whom, even after the checklist moves
on. Deleting a built package leaves the checklist and its files untouched.
