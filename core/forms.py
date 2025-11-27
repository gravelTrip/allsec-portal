from django import forms
from .models import WorkOrder, System


class WorkOrderForm(forms.ModelForm):
    systems = forms.ModelMultipleChoiceField(
        queryset=System.objects.all(),
        required=False,
        widget=forms.MultipleHiddenInput,  # <-- TU DODAJEMY
    )

    class Meta:
        model = WorkOrder
        fields = [
            "work_type",
            "title",
            "description",
            "site",
            "systems",
            "priority",
            "status",
            "planned_date",
            "requested_by",
            "assigned_to",
        ]
        widgets = {
            "work_type": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "status": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "priority": forms.Select(attrs={"class": "form-select form-select-sm"}),

            "title": forms.TextInput(attrs={"class": "form-control form-control-sm"}),

            "planned_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control form-control-sm"}
            ),

            "site": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "requested_by": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "assigned_to": forms.Select(attrs={"class": "form-select form-select-sm"}),

            # ⛔ USUŃ STĄD WPIS "systems": ...  – już go nie potrzebujemy
            "description": forms.Textarea(
                attrs={"class": "form-control form-control-sm", "rows": 4}
            ),
        }


    def clean_systems(self):
        systems = self.cleaned_data.get("systems")
        site = self.cleaned_data.get("site")

        if site and systems:
            invalid = systems.exclude(site=site)
            if invalid.exists():
                raise forms.ValidationError(
                    "Wybrano systemy, które nie należą do wybranego obiektu."
                )
        return systems
