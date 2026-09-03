#!/usr/bin/env bash
# Pull a full backup (database + documents) to somewhere that is not the server.
#
#   ./scripts/pull_backup.sh
#   ./scripts/pull_backup.sh --dest /mnt/c/Users/you/OneDrive/avl-backups
#
# Reads AVL_URL and AVL_BACKUP_TOKEN from the environment, or from a .env.backup
# file beside this script so the token is not baked into a scheduler entry.
#
# The point of the checks below: curl -o happily writes an error page over a good
# backup. A 404 saved as avl_full.tar.gz looks like a backup right up until the
# day you need it.
set -euo pipefail
cd "$(dirname "$0")/.."

DEST="${AVL_BACKUP_DIR:-./backups/offbox}"
KEEP="${AVL_BACKUP_KEEP:-30}"
[ -f .env.backup ] && { set -a; . ./.env.backup; set +a; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dest) DEST="$2"; shift 2 ;;
        --keep) KEEP="$2"; shift 2 ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

: "${AVL_URL:?set AVL_URL, e.g. https://avl-manager.onrender.com}"
: "${AVL_BACKUP_TOKEN:?set AVL_BACKUP_TOKEN to the BACKUP_TOKEN from the server}"

mkdir -p "$DEST"
STAMP=$(date +%Y%m%d_%H%M%S)
FINAL="$DEST/avl_full_$STAMP.tar.gz"
TMP=$(mktemp "${TMPDIR:-/tmp}/avl_pull_XXXXXX.tar.gz")
trap 'rm -f "$TMP"' EXIT

code=$(curl -sS --fail-with-body --max-time 600 \
            -o "$TMP" -w '%{http_code}' \
            "$AVL_URL/backup/$AVL_BACKUP_TOKEN?full=1" || true)

if [ "$code" != "200" ]; then
    echo "backup FAILED: HTTP $code" >&2
    echo "  404 means the token does not match, or the server has no BACKUP_TOKEN set." >&2
    head -c 200 "$TMP" >&2 2>/dev/null || true; echo >&2
    exit 1
fi

# Only trust it if it is really a gzip archive containing the database.
# Listed once into a variable rather than piped: under `set -o pipefail`, grep -q
# exits on its first match, tar takes SIGPIPE, and the pipeline reports failure
# even though the file was found - which would reject every good backup.
if ! listing=$(tar -tzf "$TMP" 2>/dev/null); then
    echo "backup FAILED: the download is not a readable archive" >&2
    head -c 200 "$TMP" >&2; echo >&2
    exit 1
fi
if ! grep -q '/avl\.db$' <<<"$listing"; then
    echo "backup FAILED: the archive contains no database" >&2
    exit 1
fi

mv "$TMP" "$FINAL"; trap - EXIT
# Files only: entries ending in / are directories, and counting data_uploads/packages/
# as a document would overstate what was captured.
docs=$(grep 'data_uploads/' <<<"$listing" | grep -v '/$' | wc -l)
echo "backup ok: $FINAL ($(du -h "$FINAL" | cut -f1), $docs document(s))"

# Prune oldest, keeping the most recent $KEEP. Only ever touches our own files.
mapfile -t old_files < <(ls -1t "$DEST"/avl_full_*.tar.gz 2>/dev/null | tail -n "+$((KEEP+1))" || true)
for old in "${old_files[@]:-}"; do
    [ -n "$old" ] || continue
    rm -f -- "$old" && echo "  pruned $(basename "$old")"
done
