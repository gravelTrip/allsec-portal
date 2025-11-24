from django.contrib import admin
from .models import Entity, Site, Contact, SiteContact, System



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


    
@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "entity", "city", "site_type", "updated_at")
    search_fields = ("name", "city", "entity__name")
    list_filter = ("site_type", "city")
    inlines = [SiteContactInline, SystemInline]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("__str__", "phone", "email", "company", "updated_at")
    search_fields = ("first_name", "last_name", "email", "phone", "company")


@admin.register(SiteContact)
class SiteContactAdmin(admin.ModelAdmin):
    list_display = ("site", "contact", "role", "is_default_for_notifications")
    list_filter = ("role", "is_default_for_notifications")
    search_fields = ("site__name", "contact__first_name", "contact__last_name", "contact__email")


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "system_type", "manufacturer", "model", "updated_at")
    search_fields = ("name", "site__name", "manufacturer", "model")
    list_filter = ("system_type", "manufacturer")
