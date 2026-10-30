"""Tests for SEC-REQ-10: secrets come only from environment variables."""
import os
import re
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

SETTINGS_FILE = settings.BASE_DIR / "hms" / "settings.py"
ENV_EXAMPLE = settings.BASE_DIR / ".env.example"
ENV_READ = re.compile(r'(?:os\.environ\.get|env_bool)\(\s*"([A-Z0-9_]+)"')


class SecretsFromEnvironmentTests(SimpleTestCase):
    def test_sec_req10_settings_reads_secrets_from_env(self):
        text = SETTINGS_FILE.read_text(encoding="utf-8")
        self.assertRegex(text, r'SECRET_KEY = os\.environ\.get\("DJANGO_SECRET_KEY"')
        self.assertRegex(text, r'"PASSWORD": os\.environ\.get\("DB_PASSWORD"')
        self.assertRegex(text, r'"USER": os\.environ\.get\("DB_USER"')
        self.assertRegex(text, r'EMAIL_HOST_PASSWORD = os\.environ\.get\("EMAIL_HOST_PASSWORD"')
        self.assertNotIn("django-insecure-", text)

        read = set(ENV_READ.findall(text))
        self.assertIn("DJANGO_SECRET_KEY", read)
        listed = {line.split("=", 1)[0].strip() for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
                  if "=" in line and not line.lstrip().startswith("#")}
        self.assertEqual(read - listed, set(), "add these to .env.example")

    def test_sec_req10_env_example_has_placeholders_only(self):
        values = dict(line.split("=", 1) for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
                      if "=" in line and not line.lstrip().startswith("#"))
        self.assertEqual(values["DB_PASSWORD"], "")
        self.assertEqual(values["EMAIL_HOST_PASSWORD"], "")
        self.assertIn("change-me", values["DJANGO_SECRET_KEY"])

    def test_sec_req10_production_refuses_placeholder_secret_key(self):
        env = {**os.environ, "DJANGO_DEBUG": "False", "DJANGO_SECRET_KEY": settings.DEV_SECRET_KEY}
        result = subprocess.run([sys.executable, "-c", "import hms.settings"], cwd=settings.BASE_DIR, env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set DJANGO_SECRET_KEY", result.stderr)
