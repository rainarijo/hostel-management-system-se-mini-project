import re

from django import forms

from apps.rooms.models import RoomType
from apps.students.models import MasterStudent

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


class ApplicationForm(forms.Form):
    """FR-4.2: up to three distinct room-type preferences in priority order, optional roommate SRN."""
    preference_1 = forms.ChoiceField(label="First preference")
    preference_2 = forms.ChoiceField(label="Second preference", required=False)
    preference_3 = forms.ChoiceField(label="Third preference", required=False)
    preferred_roommate_srn = forms.CharField(label="Preferred roommate SRN", max_length=13, required=False,
                                             help_text="Optional, for example PES1UG24CS001.")

    PREFERENCE_FIELDS = ("preference_1", "preference_2", "preference_3")

    def __init__(self, *args, student=None, vacancy=None, **kwargs):
        self.student = student
        super().__init__(*args, **kwargs)
        vacancy = vacancy or {}
        choices = [(value, f"{label} ({vacancy[value]} vacant bed{'s' if vacancy[value] != 1 else ''})"
                    if value in vacancy else label) for value, label in RoomType.choices]
        for name in self.PREFERENCE_FIELDS:
            empty = "Select a room type" if name == "preference_1" else "No preference"
            self.fields[name].choices = [("", empty)] + choices
            self.fields[name].widget.attrs["class"] = "form-select"
        self.fields["preferred_roommate_srn"].widget.attrs.update(
            {"class": "form-control", "placeholder": "PES1UG24CS001", "aria-describedby": "roommate_help"})

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                self.fields[name].widget.attrs["class"] += " is-invalid"

    def clean_preferred_roommate_srn(self):
        srn = self.cleaned_data["preferred_roommate_srn"].strip().upper()
        if not srn:
            return ""
        if self.student is not None and srn == self.student.srn.upper():
            raise forms.ValidationError("Enter another student's SRN, not your own.")
        if not MasterStudent.objects.filter(srn__iexact=srn).exists():
            raise forms.ValidationError("No student with this SRN was found.")
        return srn

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("preference_3") and not cleaned.get("preference_2"):
            self.add_error("preference_2", "Choose a second preference before a third.")
        seen = set()
        for name in self.PREFERENCE_FIELDS:
            value = cleaned.get(name)
            if value and value in seen:
                self.add_error(name, "Each preference must be a different room type.")
            seen.add(value)
        return cleaned

    @property
    def preferences(self):
        return [self.cleaned_data[n] for n in self.PREFERENCE_FIELDS if self.cleaned_data.get(n)]


class RoomChangeRequestForm(forms.Form):
    reason = forms.CharField(
        label="Reason for room change",
        min_length=10,
        max_length=300,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )


class RoomChangeDecisionForm(forms.Form):
    reason = forms.CharField(
        label="Rejection reason",
        max_length=300,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )
