# Issue #30 — FR-9.1 / FR-9.2 E-mail notifications with retry

This is an **overlay package** for the Sprint-2 baseline at commit `d98adb4`.
It contains only the files that are added or replaced for issue #30. Extract it
into the repository root and allow the existing files to be overwritten.

## What this implements

- A single notification queue interface:
  `enqueue(kind, recipient_email, payload)`.
- Idempotency using the existing `(kind, entity_id, recipient_email)` database constraint.
- Eight notification kinds represented by the SRS acceptance list:
  account verification, password reset, application received, application allocated,
  application rejected, room-change approved, room-change rejected, and complaint
  status changed.
- Plain-text + HTML delivery using Django's email API.
- SMTP STARTTLS remains configured through the existing environment-backed settings
  (`EMAIL_HOST`, `EMAIL_PORT=587`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`).
- Management command `send_pending_notifications`.
- Initial delivery plus up to three retries, with a five-minute delay between failures.
- `EmailLog` entries for every delivery attempt and an audit-log entry after final failure.
- Registration, password reset, application submission, allocation, rejection, and room
  change decisions enqueue notifications in the same business transaction.
- A systemd service/timer example for one-minute dispatch in production.

The issue text says "seven message kinds", but its acceptance criterion actually names
eight distinct notifications. This implementation follows the explicit acceptance list
and the eight constants already present in the Sprint-1 code.

Complaint status transitions are intentionally not modified here because the Sprint-1
baseline does not yet contain the FR-6.3 status-transition service. Issue #27 owns that
workflow; it should call `enqueue(COMPLAINT_STATUS_CHANGED, student_email, payload)` when
it changes a complaint status. The dispatcher and message template are already included.

## Installation

1. Make sure your working tree is clean and start from `main` at the Sprint-2 baseline.

   ```powershell
   git checkout main
   git pull
   git checkout -b feature/30-email-notifications
   git status
   ```

2. Extract this ZIP into the repository root. Overwrite existing files when Windows asks.

3. Verify the changed files before running anything:

   ```powershell
   git status
   git diff -- apps/accounts/views.py apps/allocation/services.py apps/notifications/services.py
   ```

4. No database model changes are introduced by this issue, so a new migration should not
   be necessary. Still run:

   ```powershell
   python manage.py makemigrations --check
   python manage.py migrate
   ```

5. Run the focused tests:

   ```powershell
   python manage.py test apps.notifications apps.accounts apps.allocation
   ```

6. Run the complete regression suite:

   ```powershell
   python manage.py test
   flake8
   ```

7. If all checks pass, inspect the final diff:

   ```powershell
   git diff --check
   git status
   ```

8. Commit and push:

   ```powershell
   git add apps/accounts/views.py apps/allocation/services.py apps/notifications deploy/systemd
   git add templates/notifications apps/notifications/tests/test_dispatcher.py README_ISSUE_30.md
   git commit -m "Implement email notification outbox and retry for issue #30"
   git push -u origin feature/30-email-notifications
   ```

9. Open a PR into `main` and include:

   `Closes #30`

## Local delivery test

The existing settings default to Django's console email backend, so local dispatch does
not require an SMTP server. Create a pending outbox row through an application flow or
Django shell, then run:

```powershell
python manage.py send_pending_notifications
```

For real SMTP, configure these environment variables in `.env` (never commit credentials):

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<university-smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
DEFAULT_FROM_EMAIL=HMS <no-reply@your-domain>
```

`EMAIL_USE_TLS=True` is already enforced by the project's settings.

## Retry behaviour

The dispatcher treats one initial send plus three retries as four total attempts.
After attempt 1, 2, or 3 fails, the outbox remains `PENDING` and `next_attempt_at`
is moved five minutes forward. After the fourth failure, the row becomes `FAILED` and
`NOTIFICATION_DELIVERY_FAILED` is written to the audit log.

## Important regression note

Sprint-1 registration/password-reset code sent mail synchronously. This package changes
those flows to enqueue mail, as required by issue #30. If any old Sprint-1 test asserts
that `mail.outbox` is populated immediately after registration/reset, that assertion must
be changed to assert a `NotificationOutbox` row and then test delivery through
`send_pending_notifications`. The new dispatcher tests demonstrate the required pattern.
