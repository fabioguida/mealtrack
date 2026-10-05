#!/usr/bin/env bash
# Weekly backup: a consistent copy of the SQLite database (the .backup API,
# never a plain file copy) uploaded to s3://$BUCKET/backups/, where a lifecycle
# rule deletes objects after 60 days (HANDOVER.md §6). Photos are synced too.
set -euo pipefail
source /srv/mealtrack/.env
DB=/srv/mealtrack/data/mealtrack.db
STAMP=$(date +%F)
TMP=$(mktemp /tmp/mealtrack-XXXX.db)
sqlite3 "$DB" ".backup '$TMP'"
sqlite3 "$TMP" "PRAGMA integrity_check;" | grep -q ok
aws s3 cp "$TMP" "s3://$S3_BUCKET/backups/mealtrack-$STAMP.db" --only-show-errors
rm -f "$TMP"
aws s3 sync /srv/mealtrack/data/photos "s3://$S3_BUCKET/photos" --only-show-errors
echo "$(date -Is) backup ok: backups/mealtrack-$STAMP.db"
