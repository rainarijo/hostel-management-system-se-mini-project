from django import forms
from django.contrib.auth import authenticate

from apps.core.audit import log_action

from .models import User

GENERIC_ERROR = "Invalid e-mail or password."   # FR-1.3: same message for unknown e-mail and wrong password


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").lower()
        password = cleaned.get("password")
        if not email or not password:
            return cleaned

        account = User.objects.filter(email=email).first()
        if account and account.is_locked:
            log_action("LOGIN_BLOCKED_LOCKED", user=account, entity="user", entity_id=account.pk, request=self.request)
            raise forms.ValidationError("This account is temporarily locked after repeated failed attempts. "
                                        "Try again in 15 minutes.")

        user = authenticate(self.request, email=email, password=password)
        if user is None:
            if account:
                account.register_failed_login()
                log_action("LOGIN_FAILED", user=account, entity="user", entity_id=account.pk, request=self.request)
            raise forms.ValidationError(GENERIC_ERROR)

        user.reset_failed_logins()
        self.user = user
        return cleaned
