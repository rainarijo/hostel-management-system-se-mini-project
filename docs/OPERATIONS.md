# Operations: scheduled jobs, backup and restore

For the Ubuntu VM in the SAD (section 4.1.7). The app lives in `/opt/hms`, runs as the `hms` user, and reads its
settings from `/etc/hms/hms.env` (same variable names as `.env.example`, with `DB_ENGINE=postgres`).

| Job | Timer | When (IST) | Requirement |
|-----|-------|------------|-------------|
| `manage.py nightly_consistency_check` | `hms-consistency.timer` | daily 01:30 | NFR-REL-1 |
| `ops/backup.sh` | `hms-backup.timer` | daily 02:00 | NFR-SAFE-1 |
| `ops/restore_test.sh` | `hms-restore-test.timer` | 1st of each month 03:00 | NFR-SAFE-1 |

**RPO is 24 hours** (one backup a day, so at most a day of data can be lost). **RTO is 4 hours** (see "Restore by hand").

## One-time setup

1. Add the backup settings to `/etc/hms/hms.env` (or a separate `/etc/hms/backup.env`, which both scripts also read):
   ```
   BACKUP_DIR=/var/backups/hms
   BACKUP_REMOTE=backup@backup-host:/srv/backups/hms
   ```
   `BACKUP_REMOTE` must be a **different machine**.
2. As the `hms` user, put the database password in `~/.pgpass` (`chmod 600 ~/.pgpass`), never in a script:
   ```
   localhost:5432:*:hms:<password>
   ```
   The `*` lets the restore test use the scratch database `hms_restore_test` too. The `hms` database user needs
   the CREATEDB privilege for that (`ALTER ROLE hms CREATEDB;`).
3. As the `hms` user, set up an SSH key to the backup host so `rsync` runs without a prompt
   (`ssh-keygen`, then `ssh-copy-id backup@backup-host`).
4. On the backup host, keep 30 days there as well, e.g. a daily cron entry:
   `find /srv/backups/hms -name 'hms-*.dump' -mtime +30 -delete`

## Install the timers

```bash
sudo cp /opt/hms/ops/systemd/hms-*.service /opt/hms/ops/systemd/hms-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hms-consistency.timer hms-backup.timer hms-restore-test.timer
systemctl list-timers 'hms-*'          # shows the next run of each timer
```

Run a job straight away to check it works: `sudo systemctl start hms-backup.service`, then
`journalctl -u hms-backup.service`. A consistency finding or a failed restore test makes the service exit with an
error, so it shows as `failed` in `systemctl --failed`. The consistency check also e-mails every active Administrator.

`Persistent=true` means a run missed while the VM was off happens as soon as it is back on.

## Restore by hand (RTO 4 hours)

Use this after data loss or a broken database. Steps 1 to 6 normally take well under an hour; the 4-hour RTO
leaves time to fetch a dump from the backup host and to check the result.

1. **Stop the app** so nothing writes during the restore: `sudo systemctl stop hms` (and the timers:
   `sudo systemctl stop hms-consistency.timer hms-backup.timer`).
2. **Pick the dump.** The newest one is `ls -1t /var/backups/hms/hms-*.dump | head -1`. If the VM's disk is lost,
   copy it back from the backup host: `rsync backup@backup-host:/srv/backups/hms/hms-YYYYmmdd-HHMM.dump /var/backups/hms/`.
3. **Keep the broken database** for investigation instead of dropping it:
   `psql -h localhost -U postgres -c 'ALTER DATABASE hms RENAME TO hms_broken_YYYYmmdd;'`
4. **Restore:**
   ```bash
   createdb -h localhost -U hms hms
   pg_restore -h localhost -U hms --no-owner --exit-on-error --dbname=hms /var/backups/hms/hms-YYYYmmdd-HHMM.dump
   ```
5. **Check it:** `cd /opt/hms && .venv/bin/python manage.py migrate --check` and
   `.venv/bin/python manage.py nightly_consistency_check --no-email` (must print `OK: 0 double-booked beds, 0 room status mismatches`).
6. **Start again:** `sudo systemctl start hms` and `sudo systemctl start hms-consistency.timer hms-backup.timer`.
   Log in as an Administrator and open a few pages.
7. **Tell users** that changes made after the backup time (at most 24 hours, the RPO) must be entered again.

The monthly `hms-restore-test` job does steps 2, 4 and 5 automatically against `hms_restore_test`, so this procedure
is exercised every month.
