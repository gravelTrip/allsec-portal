from django import forms
from .models import WorkOrder, System


class WorkOrderForm(forms.ModelForm):
    # systems – backendowo tylko do walidacji, HTML rysujemy sami (checkboxy + JS)
    systems = forms.ModelMultipleChoiceField(
        queryset=System.objects.all(),
        required=False,
        widget=forms.MultipleHiddenInput,
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
            "visit_type",
            "planned_time_from",
            "planned_time_to",
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

            "visit_type": forms.Select(
                attrs={"class": "form-select form-select-sm"}
            ),
            "planned_time_from": forms.TimeInput(
                attrs={"type": "time", "class": "form-control form-control-sm"}
            ),
            "planned_time_to": forms.TimeInput(
                attrs={"type": "time", "class": "form-control form-control-sm"}
            ),

            "site": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "requested_by": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "assigned_to": forms.Select(attrs={"class": "form-select form-select-sm"}),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 4,
                }
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

    def clean(self):
        cleaned = super().clean()

        status = cleaned.get("status")
        visit_type = cleaned.get("visit_type")
        planned_date = cleaned.get("planned_date")
        t_from = cleaned.get("planned_time_from")
        t_to = cleaned.get("planned_time_to")
        assigned_to = cleaned.get("assigned_to")

        # --- 1. Wymagania zależne od STATUSU ---

        # Statusy, które wymagają sensownej daty wizyty
        must_have_date_statuses = {
            WorkOrder.Status.SCHEDULED,
            WorkOrder.Status.IN_PROGRESS,
            WorkOrder.Status.WAITING_FOR_DECISION,
            WorkOrder.Status.WAITING_FOR_PARTS,
            WorkOrder.Status.COMPLETED,
        }

        if status in must_have_date_statuses and not planned_date:
            self.add_error("planned_date", "Dla tego statusu musisz podać datę wizyty.")

        # Statusy, które wymagają przypisanego serwisanta
        must_have_assigned_statuses = {
            WorkOrder.Status.IN_PROGRESS,
            WorkOrder.Status.COMPLETED,
        }

        if status in must_have_assigned_statuses and not assigned_to:
            self.add_error("assigned_to", "Dla tego statusu musisz przypisać serwisanta.")

        # --- 2. Wymagania zależne od rodzaju wizyty ---

        if visit_type == WorkOrder.VisitType.WINDOW:
            # dla przedziału godzinowego muszą być obie godziny
            if not t_from or not t_to:
                msg = "Dla wizyty 'na przedział godzinowy' podaj obie godziny."
                self.add_error("planned_time_from", msg)
                self.add_error("planned_time_to", msg)
            else:
                if t_from >= t_to:
                    msg = "Godzina 'od' musi być wcześniejsza niż 'do'."
                    self.add_error("planned_time_from", msg)
                    self.add_error("planned_time_to", msg)
        else:
            # dla 'W ciągu dnia' czyścimy godziny, żeby nie wisiały stare wartości
            cleaned["planned_time_from"] = None
            cleaned["planned_time_to"] = None

        return cleaned
