from django import forms

from .models import WorkOrder


class WorkOrderForm(forms.ModelForm):
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
                attrs={
                    "type": "date",
                    "class": "form-control form-control-sm",
                }
            ),

            "site": forms.Select(attrs={"class": "form-select form-select-sm"}),
            # jeśli requested_by jest ForeignKey do Contact – Select jest OK.
            # Jeśli dostałbyś błąd, zmienimy na TextInput.
            "requested_by": forms.Select(attrs={"class": "form-select form-select-sm"}),

            "assigned_to": forms.Select(attrs={"class": "form-select form-select-sm"}),

            "systems": forms.SelectMultiple(
                attrs={
                    "class": "form-select form-select-sm",
                    "size": 6,
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 4,
                }
            ),
        }
        help_texts = {
            "systems": "Wybierz systemy, których dotyczy zlecenie (przytrzymaj Ctrl, aby zaznaczyć wiele).",
        }
