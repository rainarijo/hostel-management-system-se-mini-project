from django import forms

from apps.rooms.models import Hostel

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    """FR-9.3: form for a Warden to post an announcement to an assigned hostel."""

    class Meta:
        model = Announcement
        fields = ["hostel", "title", "body", "expiry_date"]
        widgets = {
            "hostel": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 100}),
            "body": forms.Textarea(attrs={"class": "form-control", "maxlength": 2000, "rows": 6}),
            "expiry_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        warden = kwargs.pop("warden")
        super().__init__(*args, **kwargs)
        self.fields["hostel"].queryset = Hostel.objects.filter(
            wardens=warden, is_active=True
        ).order_by("name")
        self.fields["hostel"].help_text = "Only your active hostels are available."

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data["expiry_date"]
        from django.utils import timezone

        if expiry_date < timezone.localdate():
            raise forms.ValidationError("Expiry date cannot be in the past.")
        return expiry_date
