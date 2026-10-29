from django import forms


class ReportFilterForm(forms.Form):
    hostel = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All authorized hostels",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, hostels, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hostel"].queryset = hostels

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "End date cannot be before start date.")
        return cleaned
