from django import forms

from .models import ComplaintCategory, ComplaintStatus


class ComplaintForm(forms.Form):
    """FR-6.1 complaint creation form."""
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


class ComplaintStatusForm(forms.Form):
    """FR-6.3: one permitted next status plus a mandatory Warden remark."""
    status = forms.ChoiceField(
        label="New status",
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    remark = forms.CharField(
        label="Remark",
        max_length=300,
        min_length=1,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        error_messages={"required": "Enter a remark for the status change."},
    )

    def __init__(self, *args, current_status=None, **kwargs):
        super().__init__(*args, **kwargs)
        transitions = {
            ComplaintStatus.OPEN: [
                ComplaintStatus.IN_PROGRESS,
                ComplaintStatus.REJECTED,
            ],
            ComplaintStatus.IN_PROGRESS: [
                ComplaintStatus.RESOLVED,
                ComplaintStatus.REJECTED,
            ],
        }
        choices = [
            (status, dict(ComplaintStatus.choices)[status])
            for status in transitions.get(current_status, [])
        ]
        self.fields["status"].choices = choices


class ComplaintReopenForm(forms.Form):
    """FR-6.4: explicit confirmation before reopening."""
    confirm = forms.BooleanField(
        label="I want to reopen this complaint.",
        required=True,
    )
