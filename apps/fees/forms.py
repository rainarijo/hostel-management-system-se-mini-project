from datetime import date
from decimal import Decimal

from django import forms
from django.core.validators import RegexValidator

from .models import PaymentMode


class PaymentForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        label="Amount",
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
    )
    mode = forms.ChoiceField(
        choices=PaymentMode.choices,
        label="Payment mode",
    )
    txn_reference = forms.CharField(
        max_length=30,
        required=False,
        label="Transaction reference",
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9]*$",
                message="Use only letters and numbers.",
            )
        ],
    )
    paid_on = forms.DateField(
        input_formats=["%Y-%m-%d"],
        label="Payment date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    submission_id = forms.UUIDField(widget=forms.HiddenInput())

    def clean_paid_on(self):
        value = self.cleaned_data["paid_on"]
        if value > date.today():
            raise forms.ValidationError("Payment date cannot be in the future.")
        return value

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        reference = (cleaned.get("txn_reference") or "").strip()

        if mode and mode != PaymentMode.CASH and not reference:
            self.add_error(
                "txn_reference",
                "Transaction reference is required for non-cash payments.",
            )
        if mode == PaymentMode.CASH:
            cleaned["txn_reference"] = ""
        else:
            cleaned["txn_reference"] = reference
        return cleaned
