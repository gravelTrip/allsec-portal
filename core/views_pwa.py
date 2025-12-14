from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from .models import WorkOrder

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Site, System

from django.db.models import Case, When, Value, IntegerField 

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

@login_required
def pwa_home(request):
    today = date.today()

    workorders_today = (
    WorkOrder.objects
    .select_related("site")
    .prefetch_related("systems")
    .filter(assigned_to=request.user, planned_date=today)
    .order_by("planned_time_from", "planned_time_to", "id")
)
    workorders_today = _attach_workorder_system_badges(list(workorders_today))

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

def _attach_workorder_system_badges(workorders):
    # mapowanie wartości choices -> label (np. "CCTV", "SSP"...)
    choices = dict(System._meta.get_field("system_type").choices)

    for wo in workorders:
        seen = set()
        labels = []
        for s in wo.systems.all():
            key = getattr(s, "system_type", None)
            if not key or key in seen:
                continue
            seen.add(key)
            labels.append(choices.get(key, str(key)))

        wo.pwa_system_badges = labels[:4]
        wo.pwa_system_badges_more = max(0, len(labels) - 4)

    return workorders


@login_required
def pwa_workorder_list(request):
    workorders = (
        WorkOrder.objects
        .select_related("site")
        .filter(assigned_to=request.user)
        .prefetch_related("systems")
        .annotate(
            _no_date=Case(
                When(planned_date__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("_no_date", "planned_date", "planned_time_from", "planned_time_to", "id")
    )

    workorders = _attach_workorder_system_badges(list(workorders))


    return render(
        request,
        "pwa/workorder_list.html",
        {"workorders": workorders},
    )

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
    back = request.GET.get("back", "")
    back_url = reverse("core:pwa_home")

    if back and url_has_allowed_host_and_scheme(
        back,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        back_url = back

    return render(request, "pwa/objects.html", {"back_url": back_url})



@require_GET
def pwa_sw(request):
    js = r"""
const CACHE_NAME = "allsec-pwa-shell-v3";
const SHELL_URLS = [
  "/pwa/",
  "/pwa/zlecenia/",
  "/pwa/obiekty/",
  "/static/css/main.css",
  "/static/pwa/pwa.js",
  "/static/pwa/idb.js",
  "/static/pwa/objects.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k)))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (url.origin !== self.location.origin) return;
  if (req.method !== "GET") return;
  if (url.pathname.startsWith("/api/")) return; // dane są w IndexedDB

  // NAWIGACJA (HTML) -> offline fallback na /pwa/
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(async () => {
        const cached = await caches.match(url.pathname, { ignoreSearch: true });
        return cached || caches.match("/pwa/", { ignoreSearch: true });
      })
    );
    return;
  }

  // STATYKI / PWA -> cache-first
  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((resp) => {
        if (url.pathname.startsWith("/static/") || url.pathname.startsWith("/pwa/")) {
          caches.open(CACHE_NAME).then((cache) => cache.put(req, resp.clone()));
        }
        return resp;
      });
    })
  );
});
"""
    return HttpResponse(js, content_type="application/javascript")

@require_GET
@login_required
def api_pwa_ping(request):
    return JsonResponse({"ok": True, "server_time": timezone.now().isoformat()})

@login_required
def pwa_workorder_detail(request, pk: int):
    wo = get_object_or_404(
        WorkOrder.objects.select_related("site").prefetch_related("systems"),
        pk=pk,
        assigned_to=request.user,
    )
    return render(request, "pwa/workorder_detail.html", {"wo": wo, "current_path": request.get_full_path()})
