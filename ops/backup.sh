#!/usr/bin/env bash
# NFR-SAFE-1: daily PostgreSQL backup at 02:00 IST (ops/systemd/hms-backup.timer), kept 30 days, copied off-machine.
# RPO 24 hours. Passwords are NOT read here: put them in ~/.pgpass of the user running this script.
#
# Settings come from the environment (EnvironmentFile=/etc/hms/hms.env) or /etc/hms/backup.env:
#   DB_NAME, DB_USER, DB_HOST, DB_PORT   same names as hms/settings.py
#   BACKUP_DIR                           local folder for dumps, e.g. /var/backups/hms
#   BACKUP_REMOTE                        user@host:/path on a different machine
set -euo pipefail

if [[ -f /etc/hms/backup.env ]]; then
    set -a
    # shellcheck disable=SC1091
    source /etc/hms/backup.env
    set +a
fi

DB_NAME="${DB_NAME:?DB_NAME is not set}"
DB_USER="${DB_USER:?DB_USER is not set}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:?BACKUP_DIR is not set}"
BACKUP_REMOTE="${BACKUP_REMOTE:?BACKUP_REMOTE is not set (user@host:/path)}"
KEEP_DAYS=30

mkdir -p "$BACKUP_DIR"
dump="$BACKUP_DIR/hms-$(date +%Y%m%d-%H%M).dump"

echo "Dumping $DB_NAME to $dump"
pg_dump --format=custom --no-password --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
    --file="$dump.partial" "$DB_NAME"
mv "$dump.partial" "$dump"          # a half-written dump never looks like a good one

echo "Copying to $BACKUP_REMOTE"
rsync --archive --partial "$dump" "$BACKUP_REMOTE/"

echo "Deleting local dumps older than $KEEP_DAYS days"
find "$BACKUP_DIR" -maxdepth 1 -name 'hms-*.dump' -mtime +30 -delete
# The 30-day retention on the remote machine is its own cron/timer: find <path> -name 'hms-*.dump' -mtime +30 -delete

echo "Backup finished: $dump"
