"""Maps the SQLite schema onto Airtable tables, fields and links.

Derived from the live SQLite schema (PRAGMA table_info / foreign_key_list) plus
the overrides below, so the mapping cannot drift as db.py grows new columns - a
new column shows up in Airtable automatically, typed by the rules here.

Airtable has no integer primary keys, so every table keeps its SQLite "id" as a
plain number field. That is what the migration links on and what lets a record
round-trip back into SQLite with its identity intact.
"""
from .. import db

# ---------------- type overrides, keyed by (table, column) ----------------

# Real calendar pickers in the templates. Everything else that merely *looks*
# like a date stays text: ie_report_items.due_date is a free-text box that
# holds things like "End Aug", and checklist eta/pct are free text too.
DATE_FIELDS = {
    ("actions", "due_date"), ("calls", "call_date"), ("packages", "rev_date"),
    ("ie_reports", "kickoff_date"), ("ie_reports", "target_date"),
}

# ISO timestamps written by the app, never by hand.
DATETIME_COLUMNS = {"created_at", "updated_at", "uploaded_at", "closed_at",
                    "last_login", "started_at", "ended_at", "ts"}

# INTEGER columns used as 0/1 flags.
BOOL_COLUMNS = {"active", "is_primary", "superseded"}

# Free prose or JSON blobs - anything a one-line box would truncate visually.
LONG_TEXT_COLUMNS = {"notes", "snapshot", "manifest", "detail", "description",
                     "review_item", "evidence", "source", "topics", "outcomes",
                     "owner_due", "gap", "stored_path"}

TYPED_TEXT_COLUMNS = {"email": "email", "website": "url", "source_url": "url",
                      "phone": "phoneNumber"}

# Columns that hold "who did this" - an address OR a marker like
# "seed:enfin-2026-06", so they must not be validated as email.
ACTOR_COLUMNS = {"created_by", "updated_by", "uploaded_by", "added_by",
                 "changed_by", "actor", "user_email", "owner", "shared_with"}

# FK-shaped columns added by later migrations without a REFERENCES clause, so
# PRAGMA foreign_key_list does not report them. Linked here by hand.
LINK_EXTRAS = {
    ("actions", "owner_person_id"): "people",
    ("actions", "product_id"): "products",
    ("actions", "checklist_item_id"): "checklist_items",
    ("checklist_items", "template_id"): "workstream_templates",
    ("packages", "template_id"): "workstream_templates",
}

# attachments.ref_id points at a different table depending on attachments.kind,
# so it cannot become a link - it stays a number and the app resolves it.
POLYMORPHIC = {("attachments", "ref_id")}

# Single-select vocabularies, from the constants the app already validates
# against. Actual stored values are unioned in at build time so nothing is
# dropped: ie_report_items.priority holds "Medium", which IE_PRIORITIES omits.
def _select_sources():
    return {
        ("listings", "status"): db.STATUSES,
        ("status_history", "old_status"): db.STATUSES,
        ("status_history", "new_status"): db.STATUSES,
        ("checklist_items", "status"): db.CHECK_STATUSES,
        ("checklist_items", "obligation"): db.OBLIGATIONS,
        ("checklist_items", "doc_category"): [],
        ("workstream_template_items", "obligation"): db.OBLIGATIONS,
        ("workstream_template_items", "doc_category"): [],
        ("products", "category"): db.CATEGORIES,
        ("products", "lifecycle"): ["Active", "Roadmap"],
        ("workstream_templates", "category"): db.CATEGORIES,
        ("ie_templates", "category"): db.CATEGORIES,
        ("people", "org"): db.ORGS,
        ("assignments", "role"): db.ROLES,
        ("contacts", "role"): db.CONTACT_ROLES,
        ("calls", "call_type"): db.CALL_TYPES,
        ("actions", "status"): ["Open", "Done"],
        ("actions", "priority"): db.ACTION_PRIORITIES,
        ("users", "role"): ["viewer", "editor", "admin"],
        ("packages", "scope"): list(db.PACKAGE_SCOPES),
        ("call_attendees", "side"): ["qcells", "tpo"],
        ("ie_templates", "reviewer"): db.IE_REVIEWERS,
        ("ie_reports", "reviewer"): db.IE_REVIEWERS,
        ("ie_reports", "status"): db.IE_REPORT_STATUSES,
        ("ie_report_items", "status"): db.IE_ITEM_STATUSES,
        ("ie_report_items", "priority"): db.IE_PRIORITIES,
        ("ie_template_items", "priority"): db.IE_PRIORITIES,
    }

# Airtable requires a primary field and it must be a plain scalar - never a
# link, checkbox or date - so whichever column is named here is forced to
# singleLineText. Tables with no natural label get a synthesized "key".
PRIMARY = {
    "users": "email", "avls": "name", "products": "name", "people": "name",
    "contacts": "name", "actions": "description", "attachments": "filename",
    "workstream_templates": "name", "workstream_template_items": "workstream",
    "checklist_items": "workstream", "packages": "label", "meta": "key",
    "ie_templates": "name", "ie_reports": "name",
    "ie_template_sections": "title", "ie_report_sections": "title",
    "call_attendees": "name",
    "ie_template_items": "review_item", "ie_report_items": "review_item",
}
SYNTHETIC_KEY = "key"

DESCRIPTIONS = {
    "users": "App sign-ins and their role (viewer / editor / admin).",
    "avls": "TPO accounts the matrix tracks.",
    "products": "Qcells products, by category and lifecycle.",
    "listings": "The status matrix: one cell per product x TPO.",
    "calls": "Call log per TPO.",
    "status_history": "Every listing status change, with who and when.",
    "people": "Qcells roster used for the trifecta pickers.",
    "assignments": "Dated record of who held which seat.",
    "actions": "Action items with owner, due date and priority.",
    "checklist_items": "Dataroom requirements per product x TPO.",
    "attachments": "Uploaded files, filed against a record.",
    "audit": "Append-only audit trail.",
    "workstream_templates": "Reusable requirement lists, scoped by category.",
    "workstream_template_items": "Requirements inside a workstream template.",
    "meta": "Internal key/value markers for one-off migrations.",
    "contacts": "TPO-side contacts.",
    "packages": "Generated dataroom submission packages.",
    "call_attendees": "Attendees on a logged call, per side.",
    "template_revisions": "Undo history for workstream templates.",
    "ie_templates": "IE / bankability review templates (DNV et al).",
    "ie_template_sections": "Sections within an IE template.",
    "ie_template_items": "Review items within an IE template section.",
    "ie_reports": "A live IE review for a product.",
    "ie_report_sections": "Sections within a live IE report.",
    "ie_report_items": "Review items being worked in a live IE report.",
    "ie_template_revisions": "Undo history for IE templates.",
}

class Field:
    def __init__(self, column, type_, options=None, link=None, primary=False,
                 synthetic=False):
        self.column, self.type, self.options = column, type_, options
        self.link, self.primary, self.synthetic = link, primary, synthetic

    @property
    def name(self):
        return self.column

    def spec(self):
        """The Airtable metadata-API payload for this field."""
        f = {"name": self.name, "type": self.type}
        if self.options:
            f["options"] = dict(self.options)
        return f

    def __repr__(self):
        return f"<Field {self.column}:{self.type}{' ->' + self.link if self.link else ''}>"

class Table:
    def __init__(self, name, fields, description=""):
        self.name, self.fields, self.description = name, fields, description

    @property
    def links(self):
        return [f for f in self.fields if f.link]

    @property
    def scalars(self):
        return [f for f in self.fields if not f.link]

    @property
    def primary_field(self):
        return self.fields[0]

    def field(self, column):
        return next((f for f in self.fields if f.column == column), None)

    def __repr__(self):
        return f"<Table {self.name} ({len(self.fields)} fields)>"

def _distinct(c, table, column):
    rows = c.execute(f'SELECT DISTINCT "{column}" FROM "{table}" '
                     f'WHERE "{column}" IS NOT NULL AND "{column}" <> ""')
    return [str(r[0]) for r in rows]

def _choices(c, table, column, curated):
    """Curated vocabulary first, then any extra value already in the data."""
    seen, out = set(), []
    for v in list(curated) + _distinct(c, table, column):
        if v not in seen:
            seen.add(v)
            out.append(v)
    return {"choices": [{"name": v} for v in out]}

def _field_type(table, column, decl_type, c, selects):
    if (table, column) in selects:
        return "singleSelect", _choices(c, table, column, selects[(table, column)])
    if decl_type == "INTEGER":
        if column in BOOL_COLUMNS:
            return "checkbox", {"icon": "check", "color": "greenBright"}
        return "number", {"precision": 0}
    if (table, column) in DATE_FIELDS:
        return "date", {"dateFormat": {"name": "iso"}}
    if column in DATETIME_COLUMNS:
        return "dateTime", {"dateFormat": {"name": "iso"},
                            "timeFormat": {"name": "24hour"},
                            "timeZone": "utc"}
    if column in ACTOR_COLUMNS:
        return "singleLineText", None
    if column in TYPED_TEXT_COLUMNS:
        return TYPED_TEXT_COLUMNS[column], None
    if column in LONG_TEXT_COLUMNS:
        return "multilineText", None
    return "singleLineText", None

def sqlite_tables(c):
    return [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name <> 'airtable_ids' ORDER BY name")]

def links_for(c, table):
    """Declared foreign keys plus the hand-declared LINK_EXTRAS."""
    out = {r["from"]: r["table"]
           for r in c.execute(f'PRAGMA foreign_key_list("{table}")')}
    for (t, col), target in LINK_EXTRAS.items():
        if t == table:
            out[col] = target
    return {k: v for k, v in out.items() if (table, k) not in POLYMORPHIC}

def build_table(c, table, selects=None):
    selects = selects if selects is not None else _select_sources()
    cols = list(c.execute(f'PRAGMA table_info("{table}")'))
    link_cols = links_for(c, table)
    primary_col = PRIMARY.get(table)

    fields = []
    if primary_col:
        fields.append(Field(primary_col, "singleLineText", primary=True))
    else:
        fields.append(Field(SYNTHETIC_KEY, "singleLineText", primary=True,
                            synthetic=True))
    for col in cols:
        name, decl = col["name"], (col["type"] or "TEXT").upper()
        if name == primary_col:
            continue                      # already emitted as the primary field
        if name in link_cols:
            fields.append(Field(name, "multipleRecordLinks",
                                link=link_cols[name]))
            continue
        ftype, opts = _field_type(table, name, decl, c, selects)
        fields.append(Field(name, ftype, opts))
    return Table(table, fields, DESCRIPTIONS.get(table, ""))

def build(c):
    """Every table, ordered so a link target is always created before its source."""
    names = sqlite_tables(c)
    selects = _select_sources()
    specs = {t: build_table(c, t, selects) for t in names}
    return [specs[n] for n in _toposort(names, {t: {f.link for f in s.links}
                                                for t, s in specs.items()})]

def _toposort(names, deps):
    """Kahn's algorithm; self-references and cycles fall back to alphabetical."""
    done, out = set(), []
    remaining = list(names)
    while remaining:
        ready = [n for n in remaining
                 if all(d in done or d == n for d in deps.get(n, ()))]
        if not ready:
            ready = [remaining[0]]        # cycle - break it, links are patched later
        for n in ready:
            out.append(n)
            done.add(n)
            remaining.remove(n)
    return out
