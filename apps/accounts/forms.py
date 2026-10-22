from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from apps.core.audit import log_action
from apps.students.models import MasterStudent, StudentProfile

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


class RegistrationForm(forms.Form):
    srn = forms.CharField(max_length=13, label="Student Registration Number")
    email = forms.EmailField(label="Institutional email")
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
    )

    def clean(self):
        cleaned = super().clean()
        srn = (cleaned.get("srn") or "").strip().upper()
        email = (cleaned.get("email") or "").strip().lower()

        if not srn or not email:
            return cleaned

        master = MasterStudent.objects.filter(
            srn__iexact=srn,
            email__iexact=email,
        ).first()

        already_registered = (
            User.objects.filter(email__iexact=email).exists()
            or StudentProfile.objects.filter(srn__iexact=srn).exists()
        )

        if not master or already_registered:
            raise forms.ValidationError(
                "SRN not found or already registered"
            )

        cleaned["srn"] = master.srn
        cleaned["email"] = master.email.lower()
        self.master_student = master
        return cleaned

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        if password2:
            validate_password(password2)

        return password2
