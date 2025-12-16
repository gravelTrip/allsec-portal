import json

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

from django.contrib import messages

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Site, System, WorkOrder, ServiceReport
from .forms import ServiceReportForm, ServiceReportPwaForm
from django.forms.models import model_to_dict

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
        .exclude(status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED])
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
        .exclude(status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED])
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
const CACHE_NAME = "allsec-pwa-shell-v4";
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
def api_pwa_workorders_dump(request):
    user = request.user

    qs = (
        WorkOrder.objects
        .select_related("site")
        .prefetch_related("systems")
        .filter(assigned_to=user)
        .exclude(status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED])
        .order_by("planned_date", "planned_time_from", "id")
    )

    # mapowanie choices system_type -> label
    type_labels = dict(System._meta.get_field("system_type").choices)

    workorders = []
    for wo in qs:
        site = wo.site
        # badge z typów systemów (unikalne)
        seen = set()
        labels = []
        sr_id = None
        sr_number = None

        # tylko dla SERWIS (żeby nie tworzyć śmieci dla innych typów)
        if wo.work_type == WorkOrder.WorkOrderType.SERVICE:
            sr, _created = ServiceReport.objects.get_or_create(
                work_order=wo,
                defaults={"created_by": request.user},
            )
            sr_id = sr.pk
            sr_number = sr.number
        for s in wo.systems.all():
            k = getattr(s, "system_type", None)
            if not k or k in seen:
                continue
            seen.add(k)
            labels.append(type_labels.get(k, str(k)))

        workorders.append({
            "id": wo.id,
            "title": wo.title,
            "status_label": wo.get_status_display(),
            "work_type_label": wo.get_work_type_display(),
            "planned_date": wo.planned_date.isoformat() if wo.planned_date else None,
            "planned_time_from": wo.planned_time_from.strftime("%H:%M") if wo.planned_time_from else None,
            "planned_time_to": wo.planned_time_to.strftime("%H:%M") if wo.planned_time_to else None,
            "site": {
                "id": site.id if site else None,
                "name": site.name if site else None,
                "street": site.street if site else None,
                "city": site.city if site else None,
            },
            "system_badges": labels[:4],
            "system_badges_more": max(0, len(labels) - 4),
            "number": wo.number,
            "description": wo.description,
            "site_id": site.id if site else None,
            "system_ids": [s.id for s in wo.systems.all()],
            "service_report_id": sr_id,
            "service_report_number": sr_number,
        })

    return JsonResponse({
        "generated_at": timezone.now().isoformat(),
        "workorders": workorders,
    })

@login_required
def pwa_workorder_detail(request, pk: int):
    wo = get_object_or_404(
        WorkOrder.objects.select_related("site").prefetch_related("systems"),
        pk=pk,
        assigned_to=request.user,
    )
    back = request.GET.get("back", "")
    back_url = reverse("core:pwa_workorder_list")

    if back and url_has_allowed_host_and_scheme(
        back,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        back_url = back

    sr = None
    if wo.work_type == WorkOrder.WorkOrderType.SERVICE:
        sr, _created = ServiceReport.objects.get_or_create(
            work_order=wo,
            defaults={"created_by": request.user},
        )


    return render(
        request,
        "pwa/workorder_detail.html",
        {
            "wo": wo,
            "current_path": request.get_full_path(),
            "back_url": back_url,
            "sr": sr,
            "sr_id": sr.pk if sr else None,
        },
    )
@login_required
def pwa_servicereport_entry(request, pk):
    wo = get_object_or_404(WorkOrder, pk=pk)

    # TODO: tu wstaw swoje zasady dostępu (np. assigned_to albo biuro)
    # if not can_access_workorder(request.user, wo): ...

    sr, created = ServiceReport.objects.get_or_create(
        work_order=wo,
        defaults={"created_by": request.user},
    )
    back = request.GET.get("back", "")
    edit_url = reverse("core:pwa_servicereport_edit", args=[sr.pk])

    if back and url_has_allowed_host_and_scheme(
        back,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        edit_url = f"{edit_url}?back={back}"

    return redirect(edit_url)


@login_required
def pwa_servicereport_edit(request, pk):
    sr = get_object_or_404(ServiceReport, pk=pk)
    wo = sr.work_order

    # TODO: tu wstaw swoje zasady dostępu
    # if not can_access_workorder(request.user, wo): ...

    form = ServiceReportPwaForm(request.POST or None, instance=sr)

    back = request.GET.get("back", "")
    back_url = reverse("core:pwa_workorder_detail", args=[wo.pk])

    if back and url_has_allowed_host_and_scheme(
        back,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        back_url = back

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Zapisano protokół.")
            return redirect(back_url)

    return render(
        request,
        "pwa/servicereport_form_pwa.html",
        {"sr": sr, "wo": wo, "form": form, "back_url": back_url},
    )

@require_POST
@login_required
def api_pwa_servicereport_save(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Bad JSON")

    sr_id = payload.get("sr_id")
    wo_id = payload.get("wo_id")
    fields = payload.get("fields") or {}

    if not sr_id or not isinstance(fields, dict):
        return HttpResponseBadRequest("Missing sr_id/fields")

    sr = get_object_or_404(ServiceReport.objects.select_related("work_order"), pk=sr_id)

    # (opcjonalnie) sanity check
    if wo_id and sr.work_order_id != int(wo_id):
        return HttpResponseBadRequest("WorkOrder mismatch")

    # Minimalna kontrola dostępu: serwisant przypisany do zlecenia albo staff/superuser
    assigned_id = getattr(sr.work_order, "assigned_to_id", None)
    if not (request.user.is_superuser or request.user.is_staff or assigned_id == request.user.id):
        return HttpResponseForbidden("Not allowed")

    # Whitelist pól = pola z formularza (czyli bez numeru/statusu itd.)
    allowed = list(ServiceReportPwaForm().fields.keys())


    # Merge obecnego stanu + incoming (żeby nie wywalać walidacji na brakujących polach)
    base = model_to_dict(sr, fields=allowed)
    for k, v in fields.items():
        if k in allowed:
            base[k] = v

    form = ServiceReportPwaForm(data=base, instance=sr)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    saved = form.save()
    return JsonResponse({"ok": True, "sr_id": saved.pk, "updated_at": saved.updated_at.isoformat()})
