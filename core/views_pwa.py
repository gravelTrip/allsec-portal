from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import WorkOrder

from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Site, System


@login_required
def pwa_home(request):
    today = date.today()

    workorders_today = (
        WorkOrder.objects
        .select_related("site")
        .filter(assigned_to=request.user, planned_date=today)
        .order_by("planned_time_from", "planned_time_to", "id")
    )

    return render(
        request,
        "pwa/home.html",
        {
            "today": today,
            "workorders_today": workorders_today,
        },
    )

def _serialize_site(site: Site) -> dict:
    return {
        "id": site.id,
        "name": site.name,
        "street": site.street,
        "postal_code": site.postal_code,
        "city": site.city,
        "google_maps_url": site.google_maps_url,
        "access_info": site.access_info,
        "technical_notes": site.technical_notes,
        "updated_at": site.updated_at.isoformat() if site.updated_at else None,
    }


def _serialize_system(system: System) -> dict:
    return {
        "id": system.id,
        "site_id": system.site_id,
        "system_type": system.system_type,
        "name": system.name,
        "manufacturer": system.manufacturer,
        "model": system.model,
        "in_service_contract": system.in_service_contract,
        "commissioning_date": system.commissioning_date.isoformat() if system.commissioning_date else None,
        "last_modernization_date": system.last_modernization_date.isoformat() if system.last_modernization_date else None,
        "location_info": system.location_info,
        "access_data": system.access_data,
        "procedures": system.procedures,
        "notes": system.notes,
        "updated_at": system.updated_at.isoformat() if system.updated_at else None,
    }

@require_GET
@login_required
def api_pwa_catalog_dump(request: HttpRequest) -> JsonResponse:
    sites_qs = Site.objects.all().order_by("name", "id")
    systems_qs = System.objects.all().order_by("site_id", "system_type", "id")

    return JsonResponse(
        {
            "server_time": timezone.now().isoformat(),
            "sites": [_serialize_site(s) for s in sites_qs],
            "systems": [_serialize_system(x) for x in systems_qs],
        }
    )

@login_required
def pwa_objects(request):
    return render(request, "pwa/objects.html")