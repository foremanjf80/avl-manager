#!/usr/bin/env bash
# Nightly SQLite backup - add to cron: 0 2 * * * /path/to/scripts/backup.sh
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/backups"
STAMP=$(date +%Y%m%d_%H%M%S)
sqlite3 "$DIR/avl.db" ".backup '$DIR/backups/avl_$STAMP.db'"
ls -1t "$DIR/backups"/avl_*.db | tail -n +31 | xargs -r rm --
echo "backup written: backups/avl_$STAMP.db"
