#!/usr/bin/env bash
# NFR-SAFE-1: monthly restore test (ops/systemd/hms-restore-test.timer, 1st of the month 03:00 IST).
# Restores the newest dump into a scratch database, runs the consistency check against it, then drops it.
# Exits non-zero on any failure. Uses the same settings as ops/backup.sh; passwords come from ~/.pgpass.
set -euo pipefail

if [[ -f /etc/hms/backup.env ]]; then
    set -a
    # shellcheck disable=SC1091
    source /etc/hms/backup.env
    set +a
fi

DB_USER="${DB_USER:?DB_USER is not set}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:?BACKUP_DIR is not set}"
APP_DIR="${APP_DIR:-/opt/hms}"
PYTHON="${PYTHON:-$APP_DIR/.venv/bin/python}"
SCRATCH_DB=hms_restore_test
PG=(--no-password --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER")

latest="$(ls -1t "$BACKUP_DIR"/hms-*.dump 2>/dev/null | head -n 1 || true)"
if [[ -z "$latest" ]]; then
    echo "No backup found in $BACKUP_DIR" >&2
    exit 1
fi

cleanup() { dropdb "${PG[@]}" --if-exists "$SCRATCH_DB" || true; }
trap cleanup EXIT

echo "Restoring $latest into $SCRATCH_DB"
dropdb "${PG[@]}" --if-exists "$SCRATCH_DB"
createdb "${PG[@]}" "$SCRATCH_DB"
pg_restore "${PG[@]}" --no-owner --exit-on-error --dbname="$SCRATCH_DB" "$latest"

echo "Running the consistency check against $SCRATCH_DB"
cd "$APP_DIR"
DB_ENGINE=postgres DB_NAME="$SCRATCH_DB" "$PYTHON" manage.py nightly_consistency_check --no-email

echo "Restore test passed for $latest"
