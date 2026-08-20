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

## v12 - call log entry
The Log a call form is a real form now, not inputs injected by JavaScript, and
calls can finally be edited and deleted rather than only appended.

Attendees are picked, not typed: Qcells attendees come from the Team roster, TPO
attendees from that AVL's contact list (the picker follows the AVL dropdown). A
free-text "Other / guests" field per side keeps one-off attendees from being
blocked. Attendees are stored structurally in call_attendees with the name kept
alongside, so history survives a person or contact being removed; the existing
name columns on calls are refreshed from it, leaving the CSV export and weekly
digest unchanged.

Topics covered and Outcomes / next steps are 5-row textareas that keep their line
breaks in the list view. The log also gains a search across topics, outcomes,
owner and attendees. Attendee strings entered before this change are matched back
to the roster and contact list on first start.

## v13 - navigation order + richer action items
Contacts and Team move right in the nav, next to each other just before Files:
Dashboard, Calls, Actions, Dataroom, Package, Workstreams, History, Exec,
Contacts, Team, Files, Manage, Digest, Audit.

Action items gain structure. "What needs to happen" stays free text (now a text
area), but the owner is picked from the Team roster, with an "or someone not on
the roster" field for externals; owners typed in before this are matched to the
roster on first start. An action can be tied to a TPO AVL, a product, and a
specific workstream requirement - picking a requirement sets the AVL and product
from the checklist, and the row links straight back to it. Also adds priority,
filters by open/all, AVL and owner, an overdue count, plus edit, reopen and delete
(previously actions could only be added and marked done).

## v14 - Team orgs
Org on the Team roster is no longer Sales / Products-CE / Other. It offers the
teams people actually get pulled from - Sales, Products / CE, RBO, Procurement /
Sourcing, Product Management, Engineering / Technical, Quality, Operations,
Supply Chain, Finance, Legal / Compliance, Marketing, IT, Executive - and "Other"
now prompts for the team name rather than being a bucket. A team typed that way
is offered to everyone afterwards, so the list grows with use.

Org no longer restricts the Manage seat pickers, only orders them: the teams that
usually fill a seat are listed first and everyone else under "Other teams" with
their team shown. Pulling an RBO person into an Account Manager seat, or anyone
into Product/Technical Rep, is never blocked - an org list cannot anticipate every
real staffing arrangement.

## v15 - download side of Files
The Files page gains a Download card mirroring the uploader: the same four targets
(workstream requirement, product, TPO AVL, call) plus two roll-ups - everything
for a product across all AVLs, and everything for a TPO AVL across all products
and calls. Each returns a ZIP foldered by product / document category, with
level files under 00_product-level or 00_avl-level and calls under 01_calls, plus
a MANIFEST.csv. Repeated filenames are de-duplicated rather than overwriting.
Requirement options show their file count so you can see what you are about to
fetch. Use /dataroom/package instead for a submission - that one lists gaps too.

The workstream requirement picker only offers product x TPO pairings that have a
seeded checklist, which is by design: a requirement does not exist until a
template is applied. Both Files cards now say how many of the possible
combinations have one and link to the Dataroom page to create more.

## v16 - Prod/Tech rep picker excludes Sales
Sales no longer appears in the Product/Technical rep picker at all, not even under
"Other teams" - it is not a pairing that exists. A technical person sitting on
another team gets that team on the roster and shows up under "Other teams"
instead. The AVL seats are unchanged: Sales & account teams first, everyone else
after, since a technical person covering an account is a real arrangement.

If somebody from an excluded team already holds a seat, they are still listed
under "Currently assigned" and stay selected, so opening and saving the form
cannot silently drop them. Once removed they disappear from the picker for good.
