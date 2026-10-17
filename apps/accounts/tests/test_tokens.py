"""AuthToken validity (FR-1.2: 24 h verification links, FR-1.6: 30 min reset links)."""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import AuthToken, TokenPurpose, User


class AuthTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("t@hms.local", "Strongpass2026")

    def make(self, **kw):
        return AuthToken.objects.create(user=self.user, purpose=TokenPurpose.VERIFY, token_hash=kw.pop("h", "a" * 64),
                                        expires_at=timezone.now() + timezone.timedelta(hours=24), **kw)

    def test_fresh_token_is_valid(self):
        self.assertTrue(self.make().is_valid)

    def test_used_token_is_invalid(self):
        self.assertFalse(self.make(used_at=timezone.now()).is_valid)

    def test_expired_token_is_invalid(self):
        t = self.make()
        t.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.assertFalse(t.is_valid)
