from django.contrib import admin
from .models import Entity

# Register your models here.
@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "nip", "regon", "pesel", "city", "updated_at")
    search_fields = ("name", "nip", "regon", "pesel", "city")
    list_filter = ("type",)
