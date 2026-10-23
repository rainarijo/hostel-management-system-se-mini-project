from django import forms

from apps.accounts.models import Role, User

from .models import Hostel, Room, RoomType


class BootstrapModelForm(forms.ModelForm):
    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                current = self.fields[name].widget.attrs.get("class", "")
                self.fields[name].widget.attrs["class"] = f"{current} is-invalid".strip()


class HostelForm(BootstrapModelForm):
    class Meta:
        model = Hostel
        fields = ["name", "gender_type", "wardens"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "gender_type": forms.Select(attrs={"class": "form-select"}),
            "wardens": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["wardens"].queryset = User.objects.filter(role=Role.WARDEN).order_by("email")
        self.fields["wardens"].required = True
        self.fields["wardens"].help_text = "Select one or more Wardens for this hostel."


class RoomForm(BootstrapModelForm):
    class Meta:
        model = Room
        fields = ["hostel", "room_no", "floor", "room_type", "capacity", "annual_fee", "status"]
        widgets = {
            "hostel": forms.Select(attrs={"class": "form-select"}),
            "room_no": forms.TextInput(attrs={"class": "form-control"}),
            "floor": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 20}),
            "room_type": forms.Select(attrs={"class": "form-select"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 4}),
            "annual_fee": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 500000, "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class AvailabilityFilterForm(forms.Form):
    hostel = forms.IntegerField(required=False, min_value=1, widget=forms.NumberInput(
        attrs={"class": "form-control"}))
    floor = forms.IntegerField(required=False, min_value=0, max_value=20, widget=forms.NumberInput(
        attrs={"class": "form-control"}))
    room_type = forms.CharField(required=False, max_length=10, widget=forms.TextInput(
        attrs={"class": "form-control"}))

    def clean_room_type(self):
        value = self.cleaned_data["room_type"].casefold()
        if not value:
            return ""
        for room_type in RoomType:
            if value in (room_type.value.casefold(), room_type.label.casefold()):
                return room_type.value
        raise forms.ValidationError("Select a valid room type.")


class RoomCSVImportForm(forms.Form):
    file = forms.FileField(label="Rooms CSV file", widget=forms.ClearableFileInput(
        attrs={"class": "form-control"}))

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        return uploaded_file
