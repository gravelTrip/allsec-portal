from django.contrib import admin
from django.utils.html import format_html
from .models import Entity, Manager, Site, Contact, SiteContact, System





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
    extra = 1


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
    inlines = [SiteContactInline, SystemInline]

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
