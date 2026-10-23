
from django import forms

from .models import StudentProfile
from .profile_validators import (
    validate_mobile_number,
    validate_permanent_address,
    validate_profile_photo,
)


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            "srn",
            "name",
            "gender",
            "program",
            "year",
            "mobile",
            "personal_email",
            "permanent_address",
            "guardian_name",
            "guardian_relationship",
            "guardian_mobile",
            "emergency_contact_name",
            "emergency_contact_mobile",
            "blood_group",
            "photo",
        ]
        widgets = {
            "permanent_address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)

        if not is_admin:
            readonly_fields = ["srn", "name", "gender", "program", "year"]
            for field_name in readonly_fields:
                self.fields.pop(field_name)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_mobile(self):
        return validate_mobile_number(
            self.cleaned_data.get("mobile", "")
        )

    def clean_guardian_mobile(self):
        return validate_mobile_number(
            self.cleaned_data.get("guardian_mobile", "")
        )

    def clean_emergency_contact_mobile(self):
        return validate_mobile_number(
            self.cleaned_data.get("emergency_contact_mobile", "")
        )

    def clean_permanent_address(self):
        return validate_permanent_address(
            self.cleaned_data.get("permanent_address", "")
        )

    def clean_photo(self):
        return validate_profile_photo(
            self.cleaned_data.get("photo")
        )
