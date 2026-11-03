from django import forms

from .models import District
from .utils import is_valid_mobile, normalize_mobile


class DistrictChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name_gu} / {obj.name_en}"


class ParticipantDetailsForm(forms.Form):
    name = forms.CharField(max_length=255)
    district = DistrictChoiceField(queryset=District.objects.filter(active=True))
    mobile = forms.CharField(max_length=20)
    school_name = forms.CharField(max_length=255)
    designation = forms.CharField(max_length=255, required=False)

    def clean_mobile(self):
        mobile = normalize_mobile(self.cleaned_data["mobile"])
        if not is_valid_mobile(mobile):
            raise forms.ValidationError("Enter a valid 10-digit mobile number.")
        return mobile
