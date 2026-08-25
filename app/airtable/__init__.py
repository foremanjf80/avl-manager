"""Airtable backend for the AVL Manager.

SQLite remains the live store. This package is the groundwork for moving to
Airtable: a REST client, a schema mapping derived from the SQLite schema, a
provisioner that builds the base, and a migration that moves data both ways.

Drive it from the CLI:  python -m app.airtable --help
"""
from .client import Airtable, AirtableError    # noqa: F401
from . import config, schema_map               # noqa: F401
