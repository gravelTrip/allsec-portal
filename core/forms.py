from django import forms
from django.forms import inlineformset_factory
from .models import (
    WorkOrder,
    System,
    ServiceReport,
    Site,
    Manager,
    Contact,
)


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
            "internal_notes",
            "site",
            "systems",
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
            "internal_notes": forms.Textarea(   # <<< NOWE
            attrs={
                "class": "form-control form-control-sm",
                "rows": 3,
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
    
# core/forms.py

class ServiceReportForm(forms.ModelForm):
    class Meta:
        model = ServiceReport
        # Na początek tylko "nagłówek" i treść – bez pozycji/materiałów
        fields = [
            "report_date",
            "service_mode",
            "payment_method",
            "requester_name",
            "requester_phone",
            "description_before",
            "work_performed",
            "result",
            "next_actions",
            "technicians",
            "notes_internal",
        ]
        widgets = {
            "report_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control form-control-sm",
                }
            ),
            "service_mode": forms.Select(
                attrs={
                    "class": "form-select form-select-sm",
                }
            ),
            "payment_method": forms.Select(
                attrs={
                    "class": "form-select form-select-sm",
                }
            ),
            "requester_name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                }
            ),
            "requester_phone": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "type": "tel",
                }
            ),
            "description_before": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 3,
                }
            ),
            "work_performed": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 4,
                }
            ),
            "result": forms.Select(
                attrs={
                    "class": "form-select form-select-sm",
                }
            ),
            "next_actions": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 3,
                }
            ),
            "technicians": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                }
            ),
            "notes_internal": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 3,
                }
            ),
        }
class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = [
            "entity",
            "manager",
            "name",
            "site_type",
            "street",
            "postal_code",
            "city",
            "google_maps_url",
            "access_info",
            "technical_notes",
        ]
        widgets = {
            "entity": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "manager": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "name": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "site_type": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "street": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "city": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "google_maps_url": forms.URLInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "access_info": forms.Textarea(
                attrs={"class": "form-control form-control-sm", "rows": 3}
            ),
            "technical_notes": forms.Textarea(
                attrs={"class": "form-control form-control-sm", "rows": 3}
            ),
        }


class ManagerForm(forms.ModelForm):
    class Meta:
        model = Manager
        fields = [
            "short_name",
            "full_name",
            "nip",
            "street",
            "postal_code",
            "city",
            "notes",
        ]
        widgets = {
            "short_name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "full_name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "nip": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "street": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "city": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control form-control-sm", "rows": 3}
            ),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "manager",
            "notes",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "phone": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "email": forms.EmailInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "manager": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control form-control-sm", "rows": 3}
            ),
        }

class SystemInlineForm(forms.ModelForm):
    class Meta:
        model = System
        fields = [
            "system_type",
            "name",
            "manufacturer",
            "model",
            "in_service_contract",
            "location_info",
        ]
        widgets = {
            "system_type": forms.Select(
                attrs={"class": "form-select form-select-sm"}
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "manufacturer": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "model": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "in_service_contract": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "location_info": forms.Textarea(
                attrs={
                    "class": "form-control form-control-sm",
                    "rows": 1,
                }
            ),
        }


SystemFormSet = inlineformset_factory(
    parent_model=Site,
    model=System,
    form=SystemInlineForm,
    extra=1,          # zawsze jeden pusty wiersz „na nowy system”
    can_delete=True,  # checkbox DELETE do usuwania istniejących
)
