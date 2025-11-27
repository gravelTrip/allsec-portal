from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django import forms

from .models import (
    Entity,
    Manager,
    Site,
    Contact,
    SiteContact,
    System,
    Job,
    WorkOrder,
    ServiceReport,
    ServiceReportItem,
)






# Register your models here.
@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "nip", "regon", "pesel", "city", "updated_at")
    search_fields = ("name", "nip", "regon", "pesel", "city")
    list_filter = ("type",)


class SiteContactInline(admin.TabularInline):
    model = SiteContact
    extra = 1
    autocomplete_fields = ("contact",)


class SystemInline(admin.TabularInline):
    model = System
    extra = 0
    fields = (
        "system_type",
        "manufacturer",
        "model",
        "in_service_contract",
        "details_link",
    )
    readonly_fields = ("details_link",)

    def details_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:core_system_change", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">Szczegóły</a>', url)

    details_link.short_description = "Szczegóły"

class WorkOrderInlineForSite(admin.TabularInline):
    model = WorkOrder
    extra = 0
    fields = ("title", "work_type", "status", "priority", "planned_date", "assigned_to")
    show_change_link = True

class WorkOrderInlineForJob(admin.TabularInline):
    model = WorkOrder
    extra = 0
    fields = ("title", "work_type", "status", "priority", "planned_date", "assigned_to", "site")
    show_change_link = True

class ServiceReportItemInline(admin.TabularInline):
    model = ServiceReportItem
    extra = 0
    fields = ("description", "quantity", "unit", "unit_price", "total_price", "order_index")



class ContactInlineForManager(admin.TabularInline):
    model = Contact
    extra = 0
    fields = ("first_name", "last_name", "phone", "email")
    show_change_link = True


class SiteInlineForManager(admin.TabularInline):
    model = Site
    extra = 0
    fields = ("name", "city", "site_type")
    show_change_link = True

@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ("short_name", "full_name", "nip", "city", "updated_at")
    search_fields = ("short_name", "full_name", "nip", "city", "street")
    list_filter = ("city",)
    inlines = [ContactInlineForManager, SiteInlineForManager]



    
@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "entity", "manager", "city", "site_type", "google_maps_link", "updated_at")
    search_fields = ("name", "city", "entity__name", "manager__short_name", "manager__full_name")
    list_filter = ("site_type", "city", "manager")
    inlines = [SiteContactInline, SystemInline, WorkOrderInlineForSite]

    def google_maps_link(self, obj):
        if obj.google_maps_url:
            return format_html('<a href="{}" target="_blank">Mapa</a>', obj.google_maps_url)
        return "-"
    google_maps_link.short_description = "Mapa"


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("__str__", "phone", "email", "manager", "updated_at")
    search_fields = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "manager__short_name",
        "manager__full_name",
    )
    list_filter = ("manager",)



@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "system_type", "manufacturer", "model", "updated_at")
    search_fields = ("name", "site__name", "manufacturer", "model")
    list_filter = ("system_type", "manufacturer")

    def get_model_perms(self, request):
        """
        Ukryj 'Systemy na obiektach' z listy modeli w /admin,
        ale zostaw możliwość otwierania strony szczegółów przez inline.
        """
        return {}


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "site",
        "job_type",
        "status",
        "planned_start_date",
        "planned_end_date",
        "updated_at",
    )
    search_fields = (
        "title",
        "description",
        "offer_number",
        "contract_number",
        "site__name",
        "entity__name",
        "manager__short_name",
        "manager__full_name",
    )
    list_filter = ("job_type", "status", "site__city", "manager")
    date_hierarchy = "planned_start_date"
    inlines = [WorkOrderInlineForJob]


class WorkOrderAdminForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # widget jako checkboxy
        self.fields["systems"].widget = forms.CheckboxSelectMultiple()

        qs = System.objects.none()
        site_id = self.data.get("site") or self.initial.get("site")
        if site_id:
            try:
                qs = System.objects.filter(site_id=int(site_id))
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.site_id:
            qs = System.objects.filter(site=self.instance.site)

        self.fields["systems"].queryset = qs

        # krótszy opis przy checkboxach
        self.fields["systems"].label_from_instance = (
            lambda obj: obj.name or obj.get_system_type_display()
        )

        self.fields["systems"].help_text = (
            "Zaznacz systemy, których dotyczy zlecenie. "
            "Pozostaw puste, jeśli zlecenie dotyczy całego obiektu. "
            "Jeśli nie widzisz listy systemów, najpierw wybierz Obiekt "
            "i użyj przycisku 'Zapisz i kontynuuj edycję'."
        )

    def clean(self):
        cleaned_data = super().clean()

        site = cleaned_data.get("site")
        systems = cleaned_data.get("systems")
        job = cleaned_data.get("job")
        work_type = cleaned_data.get("work_type")

        # 1) wszystkie systemy muszą należeć do wybranego obiektu
        if site and systems:
            wrong = [s for s in systems if s.site_id != site.id]
            if wrong:
                self.add_error(
                    "systems",
                    "Wszystkie wybrane systemy muszą należeć do wybranego obiektu.",
                )

        # 2) robota musi być z tego samego obiektu
        if site and job and job.site_id != site.id:
            self.add_error(
                "job",
                "Wybrana robota jest przypisana do innego obiektu niż zlecenie.",
            )

        # 3) dla typu 'Robota' wymagamy wybrania Roboty
        if work_type == WorkOrder.WorkOrderType.JOB and not job:
            self.add_error(
                "job",
                'Dla typu zlecenia "Robota / montaż (wyjazd)" wybierz konkretną robotę.',
            )

        return cleaned_data
    



@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    form = WorkOrderAdminForm

    list_display = (
        "id",
        "title",
        "site",
        "work_type",
        "status",
        "planned_date",
        "assigned_to",
        "updated_at",
    )
    list_filter = (
        "work_type",
        "status",
        "site__city",
        "site__entity",
        "site__manager",
    )
    search_fields = (
        "title",
        "description",
        "site__name",
        "job__title",
        "requested_by__first_name",
        "requested_by__last_name",
        "assigned_to__username",
    )
    date_hierarchy = "planned_date"
    # już nie używamy filter_horizontal = ("systems",)

@admin.register(ServiceReport)
class ServiceReportAdmin(admin.ModelAdmin):
    formfield_overrides = {}  # zostaw puste, na przyszłość

    list_display = (
        "number",
        "work_order",
        "report_date",
        "service_mode",
        "payment_method",
        "result",
        "updated_at",
    )
    search_fields = (
        "number",
        "work_order__title",
        "work_order__site__name",
        "requester_name",
        "requester_phone",
    )
    list_filter = ("service_mode", "payment_method", "result", "report_date")
    date_hierarchy = "report_date"
    inlines = [ServiceReportItemInline]

    # serwisant jako pole tylko do odczytu (auto z WorkOrder)
    readonly_fields = ("technicians", "number")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "work_order",
                    ("number", "report_date"),
                    ("service_mode", "payment_method"),
                )
            },
        ),
        (
            "Zgłaszający / kontakt",
            {
                "fields": (("requester_name", "requester_phone"),),
                "description": "Dane kontaktowe osoby zgłaszającej / zarządzającej obiektem.",
            },
        ),
        (
            "Opis prac",
            {
                "fields": (
                    "description_before",
                    "work_performed",
                    "result",
                    "next_actions",
                )
            },
        ),
        (
            "Pozostałe",
            {
                "fields": ("technicians", "notes_internal"),
            },
        ),
    )
