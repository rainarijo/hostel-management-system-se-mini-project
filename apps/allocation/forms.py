import re

from django import forms

from .models import ApplicationWindow

YEAR_PATTERN = re.compile(r"^(\d{4})-(\d{4})$")
YEAR_ERROR = "Enter the year as 2026-2027."


class ApplicationWindowForm(forms.ModelForm):
    """FR-4.1: one window per academic year."""

    class Meta:
        model = ApplicationWindow
        fields = ["academic_year", "start_date", "end_date"]
        widgets = {
            "academic_year": forms.TextInput(attrs={"class": "form-control", "placeholder": "2026-2027",
                                                    "aria-describedby": "year_help", "autofocus": True}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                self.fields[name].widget.attrs["class"] += " is-invalid"

    def clean_academic_year(self):
        year = self.cleaned_data["academic_year"].strip()
        match = YEAR_PATTERN.match(year)
        if not match or int(match.group(2)) != int(match.group(1)) + 1:
            raise forms.ValidationError(YEAR_ERROR)
        clash = ApplicationWindow.objects.filter(academic_year=year).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f"A window for {year} already exists. Edit that window instead.")
        return year

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        return cleaned
