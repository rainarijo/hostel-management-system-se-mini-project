$ErrorActionPreference = 'Stop'

Write-Host 'Issue #30 installer/verification' -ForegroundColor Cyan
Write-Host 'Run this script from the repository root after extracting the ZIP.'

python manage.py makemigrations --check
if ($LASTEXITCODE -ne 0) { throw 'makemigrations --check failed.' }

python manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'migrate failed.' }

python manage.py test apps.notifications apps.accounts apps.allocation
if ($LASTEXITCODE -ne 0) { throw 'Focused tests failed.' }

python manage.py test
if ($LASTEXITCODE -ne 0) { throw 'Full test suite failed.' }

flake8
if ($LASTEXITCODE -ne 0) { throw 'flake8 failed.' }

git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed.' }

Write-Host 'Issue #30 verification completed successfully.' -ForegroundColor Green
