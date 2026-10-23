
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User

PASSWORD = "Strongpass2026"


class AccountManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@hms.local",
            password=PASSWORD,
            role=Role.ADMIN,
        )
        self.warden = User.objects.create_user(
            email="warden@hms.local",
            password=PASSWORD,
            role=Role.WARDEN,
        )
        self.student = User.objects.create_user(
            email="student@hms.local",
            password=PASSWORD,
            role=Role.STUDENT,
        )

    def login_as(self, user):
        self.client.force_login(user)

    def test_only_admin_can_view_account_list(self):
        for user in (self.student, self.warden):
            self.login_as(user)
            response = self.client.get(reverse("accounts:account_list"))
            self.assertEqual(response.status_code, 403)
            self.client.logout()

        self.login_as(self.admin)
        response = self.client.get(reverse("accounts:account_list"))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_warden_account(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse("accounts:account_create"),
            {
                "email": "newwarden@hms.local",
                "first_name": "New",
                "last_name": "Warden",
                "role": Role.WARDEN,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:account_list"))
        user = User.objects.get(email="newwarden@hms.local")
        self.assertEqual(user.role, Role.WARDEN)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))

    def test_admin_can_change_account_role(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse(
                "accounts:account_change_role",
                args=[self.warden.pk],
            ),
            {"role": Role.STUDENT},
        )

        self.assertRedirects(response, reverse("accounts:account_list"))
        self.warden.refresh_from_db()
        self.assertEqual(self.warden.role, Role.STUDENT)

    def test_admin_can_deactivate_another_account(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse(
                "accounts:account_deactivate",
                args=[self.warden.pk],
            )
        )

        self.assertRedirects(response, reverse("accounts:account_list"))
        self.warden.refresh_from_db()
        self.assertFalse(self.warden.is_active)

    def test_admin_cannot_deactivate_own_account(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse(
                "accounts:account_deactivate",
                args=[self.admin.pk],
            )
        )

        self.assertRedirects(response, reverse("accounts:account_list"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_last_active_admin_cannot_be_demoted(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse(
                "accounts:account_change_role",
                args=[self.admin.pk],
            ),
            {"role": Role.STUDENT},
        )

        self.assertRedirects(response, reverse("accounts:account_list"))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, Role.ADMIN)

    def test_last_active_admin_cannot_be_deactivated(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse(
                "accounts:account_deactivate",
                args=[self.admin.pk],
            )
        )

        self.assertRedirects(response, reverse("accounts:account_list"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_non_admin_cannot_create_account(self):
        self.login_as(self.warden)
        response = self.client.post(
            reverse("accounts:account_create"),
            {
                "email": "blocked@hms.local",
                "first_name": "Blocked",
                "last_name": "User",
                "role": Role.WARDEN,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            User.objects.filter(email="blocked@hms.local").exists()
        )

    def test_role_change_requires_post(self):
        self.login_as(self.admin)
        response = self.client.get(
            reverse(
                "accounts:account_change_role",
                args=[self.warden.pk],
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_deactivation_requires_post(self):
        self.login_as(self.admin)
        response = self.client.get(
            reverse(
                "accounts:account_deactivate",
                args=[self.warden.pk],
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_non_admin_cannot_change_role(self):
        self.login_as(self.warden)
        response = self.client.post(
            reverse(
                "accounts:account_change_role",
                args=[self.student.pk],
            ),
            {"role": Role.WARDEN},
        )
        self.assertEqual(response.status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, Role.STUDENT)

    def test_non_admin_cannot_deactivate_account(self):
        self.login_as(self.warden)
        response = self.client.post(
            reverse(
                "accounts:account_deactivate",
                args=[self.student.pk],
            )
        )
        self.assertEqual(response.status_code, 403)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

    def test_invalid_role_is_rejected(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse(
                "accounts:account_change_role",
                args=[self.student.pk],
            ),
            {"role": "INVALID_ROLE"},
        )
        self.assertRedirects(response, reverse("accounts:account_list"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, Role.STUDENT)

    def test_admin_can_create_admin_account(self):
        self.login_as(self.admin)
        response = self.client.post(
            reverse("accounts:account_create"),
            {
                "email": "newadmin@hms.local",
                "first_name": "New",
                "last_name": "Admin",
                "role": Role.ADMIN,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("accounts:account_list"))
        user = User.objects.get(email="newadmin@hms.local")
        self.assertEqual(user.role, Role.ADMIN)
        self.assertTrue(user.is_active)

    def test_account_creation_rejects_duplicate_email(self):
        from apps.accounts.forms import AdminAccountCreateForm
        form = AdminAccountCreateForm(data={
            "email": self.warden.email,
            "first_name": "Another",
            "last_name": "Warden",
            "role": Role.WARDEN,
            "password1": PASSWORD,
            "password2": PASSWORD,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_account_creation_rejects_mismatched_passwords(self):
        from apps.accounts.forms import AdminAccountCreateForm
        form = AdminAccountCreateForm(data={
            "email": "newwarden@hms.local",
            "first_name": "New",
            "last_name": "Warden",
            "role": Role.WARDEN,
            "password1": PASSWORD,
            "password2": "DifferentPassword2026!",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_account_creation_rejects_invalid_role(self):
        from apps.accounts.forms import AdminAccountCreateForm
        form = AdminAccountCreateForm(data={
            "email": "newuser@hms.local",
            "first_name": "New",
            "last_name": "User",
            "role": "INVALID_ROLE",
            "password1": PASSWORD,
            "password2": PASSWORD,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_account_list_displays_role_choices(self):
        self.login_as(self.admin)
        response = self.client.get(reverse("accounts:account_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student")
        self.assertContains(response, "Warden")
        self.assertContains(response, "Administrator")
