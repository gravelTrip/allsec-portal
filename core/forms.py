from django import forms
from django.forms import inlineformset_factory
from datetime import date
from django.core.exceptions import ValidationError
from .models import (
    WorkOrder,
    System,
    ServiceReport,
    Site,
    Contact,
    SiteContact,
    Manager,
    ServiceReportItem,
    Entity,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1) Przypisany do – imię + nazwisko zamiast loginu
        assigned_field = self.fields.get("assigned_to")
        if assigned_field is not None:
            def label_for_user(user):
                full_name = f"{user.first_name} {user.last_name}".strip()
                return full_name or user.username

            assigned_field.label_from_instance = label_for_user

        # 2) Puste pierwsze opcje dla Obiektu i Osoby zgłaszającej
        site_field = self.fields.get("site")
        if site_field is not None:
            site_field.empty_label = ""

        requested_field = self.fields.get("requested_by")
        if requested_field is not None:
            requested_field.empty_label = ""

        # 3) Tytuł i opis – nie wymagamy na poziomie formularza,
        #    walidację robimy w clean() zależnie od typu zlecenia
        if "title" in self.fields:
            self.fields["title"].required = False
        if "description" in self.fields:
            self.fields["description"].required = False

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

        # --- 3. Tytuł i opis zależnie od rodzaju zlecenia ---

        work_type = cleaned.get("work_type")
        title = cleaned.get("title")
        description = cleaned.get("description")

        # Zlecenie przeglądu okresowego – MAINTENANCE
        if work_type == WorkOrder.WorkOrderType.MAINTENANCE:
            period_date = planned_date or date.today()
            period_str = period_date.strftime("%m-%Y")

            if not title:
                cleaned["title"] = f"Konserwacja {period_str}"

            if not description:
                cleaned["description"] = (
                    f"Wykonanie konserwacji okresowej na obiekcie za {period_str}"
                )

        else:
            # Dla innych typów zleceń wymagamy tytułu i opisu
            if not title:
                self.add_error("title", "To pole jest wymagane.")
            if not description:
                self.add_error("description", "To pole jest wymagane.")

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

ServiceReportItemFormSet = inlineformset_factory(
    ServiceReport,
    ServiceReportItem,
    fields=["description", "quantity", "unit", "unit_price", "total_price"],
    extra=0,           # ile pustych wierszy ma być domyślnie
    can_delete=True,
)

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
            "maintenance_frequency",
            "maintenance_start_month",
            "maintenance_custom_months",
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
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "maintenance_frequency" in self.fields:
            self.fields["maintenance_frequency"].label = "Częstotliwość konserwacji"
            self.fields["maintenance_frequency"].help_text = (
                "Brak – bez harmonogramu, Co miesiąc, Co kwartał, 2x w roku, "
                "lub według wybranych miesięcy."
            )

        if "maintenance_start_month" in self.fields:
            self.fields["maintenance_start_month"].label = "Miesiąc startowy"
            self.fields["maintenance_start_month"].help_text = (
                "Dla opcji: co miesiąc / co kwartał / 2x w roku. Np. 1 = styczeń."
            )

        if "maintenance_custom_months" in self.fields:
            self.fields["maintenance_custom_months"].label = "Miesiące konserwacji (lista)"
            self.fields["maintenance_custom_months"].help_text = (
                "Tylko dla trybu 'według wybranych miesięcy'. "
                "Podaj numery miesięcy oddzielone przecinkami, np. 1,4,7,10."
            )

class EntityForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = [
            "name",
            "type",
            "nip",
            "regon",
            "pesel",
            "street",
            "postal_code",
            "city",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "type": forms.Select(
                attrs={"class": "form-select form-select-sm"}
            ),
            "nip": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "regon": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "pesel": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "street": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "city": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "notes": forms.Textarea(
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

class BootstrapModelForm(forms.ModelForm):
    """Bazowy ModelForm, który dorzuca klasy Bootstrap do pól."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            # Tekstowe / selecty
            if isinstance(
                widget,
                (
                    forms.TextInput,
                    forms.Textarea,
                    forms.EmailInput,
                    forms.URLInput,
                    forms.NumberInput,
                    forms.DateInput,
                    forms.Select,
                ),
            ):
                widget.attrs["class"] = (existing + " form-control form-control-sm").strip()
            # Checkboxy
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = (existing + " form-check-input").strip()

class SystemForm(BootstrapModelForm):
    class Meta:
        model = System
        # Pole 'site' ustawiamy z widoku (nie pokazujemy w formularzu)
        exclude = ["site"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        field = self.fields.get("system_type")
        if not field:
            return

        st = System.SystemType

        # Docelowa lista typów, które użytkownik ma widzieć
        base_choices = [
            (st.SSP, st.SSP.label),               # System SSP
            (st.ODDYM, st.ODDYM.label),           # System Oddymiania
            (st.CCTV, st.CCTV.label),             # System CCTV
            (st.VIDEODOMOFON, st.VIDEODOMOFON.label),  # System Video/Domofonowy
            (st.KD, st.KD.label),                 # System Kontroli Dostępu
            (st.ALARM, st.ALARM.label),           # System SSWiN
            (st.TVSAT, st.TVSAT.label),           # System RTV/SAT
            (st.SWIATLOWOD, st.SWIATLOWOD.label), # Sieci LAN/OPTO
            (st.INNY, st.INNY.label),             # Inny system
        ]

        # Jeżeli edytujemy stary system typu DOMOFON,
        # to dodajemy tę opcję, żeby formularz się nie wywalał
        if (
            self.instance is not None
            and getattr(self.instance, "pk", None)
            and self.instance.system_type == st.DOMOFON
        ):
            base_choices = [(st.DOMOFON, st.DOMOFON.label)] + base_choices

        field.choices = base_choices


class SiteContactForm(BootstrapModelForm):
    class Meta:
        model = SiteContact
        # 'site' też ustawiamy z widoku
        exclude = ["site"]
