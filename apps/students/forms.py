
from django import forms

from .models import StudentProfile


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
