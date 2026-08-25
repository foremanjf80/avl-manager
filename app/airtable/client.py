"""Airtable REST client: auth, rate limiting, retries, pagination, batching.

Wraps both APIs the migration needs - the records API (/v0/{base}/{table}) and
the metadata API (/v0/meta/...) that creates bases, tables and fields.
"""
import time, httpx
from . import config

class AirtableError(RuntimeError):
    """An Airtable API call that failed in a way retrying will not fix."""
    def __init__(self, method, url, status, payload):
        self.status, self.payload = status, payload
        err = (payload or {}).get("error") if isinstance(payload, dict) else None
        detail = err.get("message") if isinstance(err, dict) else (err or payload)
        super().__init__(f"{method} {url} -> {status}: {detail}")

class _Rate:
    """Spaces calls so we never hand Airtable a 6th request in one second."""
    def __init__(self, per_second):
        self._interval = 1.0 / max(per_second, 0.1)
        self._next = 0.0

    def wait(self):
        now = time.monotonic()
        if now < self._next:
            time.sleep(self._next - now)
        self._next = max(now, self._next) + self._interval

# Transient statuses. 429 is the rate limiter; 5xx is Airtable having a moment.
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 5

class Airtable:
    def __init__(self, pat=None, base=None, rate=None, timeout=None, client=None):
        self.pat = pat or config.pat()
        if not self.pat:
            raise RuntimeError("AIRTABLE_PAT is not set")
        self.base = base or config.base_id()
        self._rate = _Rate(rate or config.rate_limit())
        self._http = client or httpx.Client(
            timeout=timeout or config.timeout(),
            headers={"Authorization": f"Bearer {self.pat}",
                     "Content-Type": "application/json"})

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------------- transport ----------------
    def request(self, method, url, **kw):
        last = None
        for attempt in range(MAX_RETRIES):
            self._rate.wait()
            try:
                r = self._http.request(method, url, **kw)
            except httpx.TransportError as e:      # DNS blip, reset connection
                last = e
                time.sleep(2 ** attempt)
                continue
            if r.status_code < 300:
                return r.json() if r.content else {}
            payload = _json(r)
            if r.status_code not in RETRY_STATUS:
                raise AirtableError(method, url, r.status_code, payload)
            # Airtable's 429 lockout is 30s; honour Retry-After when it sends one.
            wait = float(r.headers.get("Retry-After") or 0) or min(30, 2 ** attempt)
            last = AirtableError(method, url, r.status_code, payload)
            time.sleep(wait)
        raise last if isinstance(last, Exception) else RuntimeError("request failed")

    # ---------------- records API ----------------
    def _records_url(self, table, base=None):
        return f"{config.API_URL}/{base or self.base}/{table}"

    def list_records(self, table, fields=None, formula=None, sort=None, base=None):
        """Yield every record, following Airtable's offset pagination."""
        url, params, offset = self._records_url(table, base), {"pageSize": config.MAX_PAGE}, None
        if fields:
            params["fields[]"] = list(fields)
        if formula:
            params["filterByFormula"] = formula
        if sort:
            for i, (fld, direction) in enumerate(sort):
                params[f"sort[{i}][field]"] = fld
                params[f"sort[{i}][direction]"] = direction
        while True:
            q = dict(params)
            if offset:
                q["offset"] = offset
            page = self.request("GET", url, params=q)
            for rec in page.get("records", []):
                yield rec
            offset = page.get("offset")
            if not offset:
                return

    def create_records(self, table, records, typecast=True, base=None):
        """records: [{field: value}, ...] -> created records, in order."""
        return self._write("POST", table, records, typecast, base,
                           lambda r: {"fields": r})

    def update_records(self, table, updates, typecast=True, base=None):
        """updates: [{"id": recId, "fields": {...}}, ...]"""
        return self._write("PATCH", table, updates, typecast, base, lambda r: r)

    def _write(self, method, table, rows, typecast, base, shape):
        url, out = self._records_url(table, base), []
        for chunk in _chunks(list(rows), config.MAX_BATCH):
            body = {"records": [shape(r) for r in chunk], "typecast": bool(typecast)}
            out += self.request(method, url, json=body).get("records", [])
        return out

    def delete_records(self, table, record_ids, base=None):
        url, out = self._records_url(table, base), []
        for chunk in _chunks(list(record_ids), config.MAX_BATCH):
            out += self.request("DELETE", url,
                                params={"records[]": chunk}).get("records", [])
        return out

    # ---------------- metadata API ----------------
    def list_bases(self):
        bases, offset = [], None
        while True:
            params = {"offset": offset} if offset else {}
            page = self.request("GET", f"{config.META_URL}/bases", params=params)
            bases += page.get("bases", [])
            offset = page.get("offset")
            if not offset:
                return bases

    def create_base(self, name, workspace_id, tables):
        """Airtable requires at least one table in the create-base payload."""
        return self.request("POST", f"{config.META_URL}/bases",
                            json={"name": name, "workspaceId": workspace_id,
                                  "tables": tables})

    def base_schema(self, base=None):
        return self.request(
            "GET", f"{config.META_URL}/bases/{base or self.base}/tables")

    def create_table(self, name, fields, description=None, base=None):
        body = {"name": name, "fields": fields}
        if description:
            body["description"] = description[:20000]
        return self.request(
            "POST", f"{config.META_URL}/bases/{base or self.base}/tables", json=body)

    def create_field(self, table_id, field, base=None):
        return self.request(
            "POST",
            f"{config.META_URL}/bases/{base or self.base}/tables/{table_id}/fields",
            json=field)

def _json(r):
    try:
        return r.json()
    except ValueError:
        return {"error": r.text[:500]}

def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
