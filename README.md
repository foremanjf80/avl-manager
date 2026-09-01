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

## v17 - template undo, package revisions, dataroom summary
Workstream templates get an undo. Every change - add, edit, delete, rename,
rescope, retire - snapshots the template first, and the Recent changes list on
/workstreams offers Undo on the latest or Revert to here on any earlier point.
The undo is itself recorded, so a rollback can be rolled back. History is capped
at 40 entries per template. Checklists already seeded are not touched; re-apply
the template from the Dataroom page to push a change through.

Dataroom packages are now revisioned. Each build takes the next revision for that
product x TPO (R01, R02, ...) with an editable revision date, supersedes the
previous one, and names the ZIP <AVL>_<Product>_R0n_<date>.zip. The history table
shows revision, date, gaps and untracked counts, and which one is current.

Each package carries an auto-generated DATAROOM_SUMMARY.txt plus SUMMARY.csv,
comparing the checklist against the template it was seeded from and sorting every
requirement into three outcomes:
  INCLUDED          on the checklist with a document in the package
  NO DOCUMENT       on the checklist, nothing attached
  NOT ON CHECKLIST  in the template but never seeded here (the template changed
                    after seeding, so the checklist is behind)
The summary opens with the revision code, date, scope and template compared
against, then a per-category rollup, then the full index. The package page warns
about the third case before you build and links back to the Dataroom to re-apply
the template in Merge mode.

## v18 - IE / DNV technology reviews
A separate /ie tab for Independent Engineering reviews, deliberately not mixed
with the AVL workstream templates: an IE review is a document a third party
writes about a product, not a per-TPO dataroom checklist. Its own ie_* tables
throughout; nothing in the dataroom side changes.

Reviews are scoped to a product, since a review is commissioned once and shown to
several financiers (the AVLs it has been shared with are recorded as a note).
Each report records reviewer (DNV, Black & Veatch, Leidos, PVEL, RETC, Other),
status, kickoff and target dates.

/ie/templates manages the section-and-item structure: add or remove whole
sections, add/edit/remove review items, copy a template, and undo any change from
a Recent changes list. Starting a review copies the template into the report, so
later template edits never disturb a review already under way.

Seeded from the G4 ESS DNV Technology Review workbook (Aug 2026): 12 sections,
79 review items, each with its Item ID, sub-section, review question, required
evidence, suggested owner, priority and DNV benchmark reference.

A report page shows a per-section rollup (accepted / in progress / blocked / not
started / critical still open / evidence files) with filters for open, critical,
blocked and no-evidence. Each item takes a status, roster-backed owner, due date
and gap/action, and evidence attaches inline. Download evidence pack produces a
ZIP foldered by section with MANIFEST.csv, IE_SUMMARY.csv and IE_SUMMARY.txt,
the last classifying every item as INCLUDED or NO EVIDENCE and listing the gaps.

## v19 - IE evidence on the Files page
The Files page now has two clearly separated blocks. "AVL dataroom" keeps the
existing upload and download over workstream requirements, products, TPO AVLs and
calls. "DNV / IE evidence" is its own pair of cards below it, with a report ->
section -> review item picker for upload, and three download scopes: one review
item, one report section, or the whole report foldered by section (the same pack
as the button on the report page). Neither block offers the other's targets.

The attachment list gains an IE filter, labels IE files as
product / reviewer / section / item, and offers IE review items as their own
"DNV / IE review item" group at the end of the Re-file dropdown - so a document
can be moved between the two worlds when it genuinely serves both, without the
pickers ever mixing them.

## v20 - second IE baseline: G2 AC Module / Microinverter
Adds "DNV AC Module / Microinverter Technology Review (G2 baseline)", scoped to
AC Module: 9 sections, 69 review items, imported from the G2 Q.MI / AC Module /
ACCB DNV Technology Review workbook (Aug 2026).

  01 Company Eval                  1. Company and Business Evaluation        4
  02 System Overview               2. System Overview                        5
  03 PV Tech Eval                  3. PV Module Technical Evaluation         4
  04 ACM Tech Eval                 4. AC Module Technical Evaluation         3
  05 MI Tech Eval                  5. Microinverter Technical Evaluation    10
  06 AC Combiner Tech Eval         6. AC Combiner Technical Evaluation       7
  07 PV MFG Eval                   7. PV / ACM Manufacturing Evaluation     16
  08 Inverter Manufacturing Eval   8. Inverter Manufacturing Evaluation     15
  09 Product Support               9. Product Support, Service and Warranty   5

Section titles and owners are taken from the real worksheet tabs, not the
workbook's "00 DNV Master Index": that index still carries the G4-ESS section
names, its counts are #REF! errors, and it lists 6 sections where the workbook
has 9. Owners were mapped from the index rows onto the tabs by subject.

Baseline seeding is now per template rather than all-or-nothing, so a database
that already had the G4 baseline picks up this one (and any future one) on the
next start without duplicating what is there.

## Airtable backend (groundwork)

SQLite is still the live store. `app/airtable/` is the groundwork for moving the
database to Airtable: the base is built and the data verified against it first,
so the cutover is a separate, reversible step.

    app/airtable/client.py      REST client - auth, 4 req/s limiter, retries,
                                pagination, 10-record batching, metadata API
    app/airtable/schema_map.py  SQLite schema -> Airtable tables/fields/links
    app/airtable/provision.py   creates or extends the base (idempotent)
    app/airtable/migrate.py     push / pull / verify
    tests/test_airtable_mapping.py   offline checks against the real avl.db

### Setup
Create a personal access token at https://airtable.com/create/tokens with
`data.records:read`, `data.records:write`, `schema.bases:read` and
`schema.bases:write`, grant it the **AVL Manager** base, then fill the
`AIRTABLE_*` values in `.env`.

    python -m app.airtable status      # what is configured
    python -m app.airtable plan        # the mapping, no network needed
    python -m app.airtable provision   # create/extend the base
    python -m app.airtable push        # copy avl.db into Airtable
    python -m app.airtable verify      # compare the two, field by field

`push` is resumable: the recId for every row is cached in a local `airtable_ids`
table, so a rerun only sends rows that have not been sent.

### How the mapping works
Airtable has no integer primary keys, so each SQLite `id` travels as a plain
number field; that is what links are resolved through and what lets a record
round-trip back into SQLite with its identity intact. Foreign keys become linked
records, which is why `push` runs in two passes - records first, links second.

Field types are keyed by `(table, column)`, not by column name, because the same
name means different things in different tables: `actions.due_date` is a real
date picker, while `ie_report_items.due_date` is a free-text box holding values
like "End Aug". Single-select vocabularies come from the constants in `db.py`
unioned with whatever is already stored, so nothing is dropped on push.

The mapping is derived from the live SQLite schema, so a new column in `db.py`
appears in `plan` automatically; `python -m app.airtable diff` reports what the
base is still missing, and `provision` adds it.

### Not done yet
The app itself still reads and writes SQLite - `AVL_BACKEND` is accepted but
`airtable` is not wired into `db.conn()`. Attachments are file paths on disk,
not Airtable attachment fields, so `data_uploads/` still has to be migrated
separately when the app moves off this box.

## v21 - Prod/Tech reps as chips
The multi-select scroll box on Manage is gone. Assigned reps show as chips with
an x to remove, and a "+ add rep" dropdown lists only people not already on that
product, grouped Technical teams first (Sales is still never offered). Each click
saves immediately and writes a dated assignment, so there is no separate Save for
reps and the Team history stays complete - removing a rep ends the assignment
rather than deleting it. The dropdown hides when everyone eligible is already
assigned, and a product with no reps reads "none assigned".

The Add product form now takes one optional Prod/Tech rep; further reps are added
from the chips on the row.

Chips lay out along the row and wrap, rather than stacking, and the remove control
is a small 16px x inside the chip. It carries its own .chipx class so the global
button rule can never restyle it into a full-size blue button. The stylesheet link
is also versioned by file mtime now, so a CSS change is not hidden behind a
browser cache.

## v23 - conditional listings, and actions on any product
New matrix status "Listed, Conditional", ordered right after Listed: a listing
that is real but carries conditions to be met to keep it, or closed out to have
it lifted. It renders as the Listed green with a hatch so it reads as listed at a
glance while still standing out, and the per-cell note is where the condition
itself goes. Exec counts it within "Listed" coverage - it is on the AVL - with a
"n cond." chip so the caveat is never lost, and a status change to it is a win in
the monthly rollup like any other listing.

Actions can now be raised against any active product at any TPO, listed or not.
Previously the product dropdown only offered products that already had a seeded
dataroom checklist, which made it impossible to log the work of getting a product
listed in the first place. Each action row shows the listing status of its
product x TPO, so chasing a listing and chasing a condition on an existing one
are tellable apart, and the form shows the current status as you pick. A new
filter narrows to actions on unlisted products, listed products, conditional
listings, or actions with no product attached. Workstream requirements are still
only offered where that product x TPO has a checklist, since a requirement does
not exist until then.

## v24 - workstream requirements attachable to any action
The requirement picker on Actions no longer depends on a seeded checklist. It
loads on demand for the chosen product x TPO and offers two groups:

  On this checklist            requirements already tracked there
  Not tracked yet - from <T>   the rest of the best-matching template

Picking an untracked one adds that single requirement to the checklist and links
the action to it. This is the normal case for a conditional listing: the
condition is usually about a requirement nobody has started tracking, and it has
to be attachable without seeding a whole template first. Picking the same one
again reuses the row rather than duplicating it, and only that requirement is
added - not the rest of the template.

Loading on demand rather than embedding: 12 products x 11 AVLs x ~80 template
items is far too much to ship in the page, so the picker calls
/actions/requirements?avl_id=&product_id= when the pair changes.

## v25 - AVL acceptance, one activity feed, dataroom workflow
Three changes that go together.

Acceptance (/acceptance and /pursuit/<avl>/<product>). Everything else in the app
is organised by function; this is organised by the thing being pursued. The
portfolio lists every product x TPO with listing status, dataroom readiness, the
last package sent, open and overdue actions, IE progress, owner, target date and
next milestone. Each record pulls those together on one page with the outstanding
required requirements, the actions, TPO contacts and recent calls, packages sent,
and a scoped activity feed. Dashboard cells link straight to it.

Listings gain pursuit fields - owner, target listing date, submitted date,
condition, next milestone, risk, priority. Deliberately no second phase enum:
status already says where a pursuit stands, and two taxonomies would drift apart.

Activity (/activity) replaces History and Audit, which are now redirects. One
stream over the audit log and the status changelog, filtered by event type, TPO,
product, person, month and free text, exportable as CSV. Audit rows now carry
avl_id / product_id / entity so they can be filtered at all - older rows are
backfilled only where a name matched unambiguously. The same feed, scoped, is
what the acceptance record shows.

Dataroom workflow. "Complete" splits into Complete (we hold it) -> Submitted
(sent to the TPO) -> Accepted (they took it); all three count as done, and the
tracker reports accepted separately. Requirements gain a real due date beside the
loose ETA text, and overdue rows show red. A per-category bulk control sets owner,
due date or status across a whole document category at once. /dataroom/queue
lists requirements across every product x TPO, filtered by owner, status, TPO or
overdue - the view a person works their own list from.

Fixes: /dataroom/{iid} shadowed /dataroom/bulk, so the row update moved to
/dataroom/item/{iid}/update; and adding due_date to checklist_items made the
ORDER BY in the actions query ambiguous against actions.due_date.

## v26 - the DNV/IE report as a dataroom line item
A dataroom requirement can now point at the IE review that answers it. The IE
report is itself a line item on every AVL dataroom, so the two were being kept in
step by hand.

On the checklist, any requirement offers a "link IE review" control - but only
for products that actually have a review, so it never clutters the rest. A linked
requirement shows the review live: reviewer, status and items accepted, with a
link through to it. Only a review of that same product can be linked; anything
else is refused rather than silently accepted. Unlinking is one click.

The IE report page carries the other direction, listing the dataroom requirements
it answers across every TPO, with links back to each checklist and acceptance
record.

Packages stop calling a linked requirement a plain gap. A requirement with no
attached file but a linked review reads:
  DATAROOM_SUMMARY.txt   [~] IE REVIEW ... covered by: <report> - <status>, n/m accepted
  SUMMARY.csv            IE REVIEW - DNV Planning, 0/79 accepted
  MANIFEST.csv           COVERED BY IE REVIEW (<report>)
and the headline counts those separately from requirements nobody has started.
Genuinely missing requirements still read NO DOCUMENT.

Fix: the package page's template-drift warning had been rendered twice since v17,
once spliced into the middle of the "what will be sent" sentence.
