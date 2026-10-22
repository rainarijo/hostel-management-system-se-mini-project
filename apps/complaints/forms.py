from django import forms

from .models import ComplaintCategory


class ComplaintForm(forms.Form):
    """FR-6.1: category and a description of 20-500 characters. The photo is added in Sprint 2 (SEC-REQ-9)."""
    category = forms.ChoiceField(
        label="Category",
        choices=[("", "Select a category")] + list(ComplaintCategory.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": "Select a category."},
    )
    description = forms.CharField(
        label="Description",
        min_length=20,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        help_text="20 to 500 characters.",
        error_messages={"required": "Describe the problem."},
    )
