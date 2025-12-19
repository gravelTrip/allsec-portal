import json


from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

from django.contrib import messages

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Site, System, WorkOrder, ServiceReport, MaintenanceProtocol, WorkOrderEvent
from .forms import ServiceReportForm, ServiceReportPwaForm, MaintenanceProtocolForm, MaintenanceCheckItemFormSet
from django.forms.models import model_to_dict

from django.db.models import Case, When, Value, IntegerField 

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

def is_office(user):
    """Użytkownik biura: pełne prawa.
    - superuser
    - lub należy do grupy 'office'
    """
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name="office").exists()


@login_required
def pwa_home(request):
    today = date.today()

    workorders_today = (
        WorkOrder.objects
        .select_related("site")
        .prefetch_related("systems")
        .filter(
            assigned_to=request.user,
            planned_date=today,
            status__in=[WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.REALIZED],
        )
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
    qs = (
        WorkOrder.objects
        .select_related("site")
        .prefetch_related("systems")
        .filter(
            assigned_to=request.user,
            status__in=[WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.REALIZED],
        )
        .order_by("planned_date", "planned_time_from", "id")
    )

    workorders = _attach_workorder_system_badges(list(qs))

    return render(
        request,
        "pwa/workorder_list.html",
        {
            "workorders": workorders,
        },
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
const CACHE_NAME = "allsec-pwa-shell-v5";
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

@require_GET
@login_required
def api_pwa_workorders_dump(request):
    user = request.user

    qs = (
        WorkOrder.objects.select_related("site", "assigned_to")
        .prefetch_related("systems")
        .filter(assigned_to=request.user)
        .filter(status__in=[WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.REALIZED])
        .order_by("planned_date", "planned_time_from", "id")
)

    type_labels = dict(System._meta.get_field("system_type").choices)

    workorders = []
    for wo in qs:
        site = wo.site

        seen = set()
        labels = []

        sr_id = None
        sr_number = None
        if wo.work_type == WorkOrder.WorkOrderType.SERVICE:
            sr, _created = ServiceReport.objects.get_or_create(work_order=wo)
            sr_id = sr.id
            sr_number = sr.number

        for s in wo.systems.all():
            k = s.system_type
            if k in seen:
                continue
            seen.add(k)
            labels.append(type_labels.get(k, k))

        workorders.append({
            "id": wo.id,
            "title": wo.title,

            "status_code": wo.status,
            "status_label": wo.get_status_display(),

            "work_type_label": wo.get_work_type_display(),
            "work_type_code": wo.work_type,
            "planned_date": wo.planned_date.isoformat() if wo.planned_date else None,
            "planned_time_from": wo.planned_time_from.strftime("%H:%M") if wo.planned_time_from else None,
            "planned_time_to": wo.planned_time_to.strftime("%H:%M") if wo.planned_time_to else None,

            "updated_at": wo.updated_at.isoformat() if getattr(wo, "updated_at", None) else None,

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

    return JsonResponse({"workorders": workorders})



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
    sr_id = None
    if wo.work_type == WorkOrder.WorkOrderType.SERVICE:
        sr, _created = ServiceReport.objects.get_or_create(
            work_order=wo,
            defaults={"created_by": request.user},
        )
        sr_id = sr.pk

    mp = None
    mp_id = None
    if wo.work_type == WorkOrder.WorkOrderType.MAINTENANCE:
        mp = MaintenanceProtocol.objects.filter(work_order=wo).first()
        mp_id = mp.pk if mp else None

    return render(
        request,
        "pwa/workorder_detail.html",
        {
            "wo": wo,
            "current_path": request.get_full_path(),
            "back_url": back_url,
            "sr": sr,
            "sr_id": sr_id,
            "mp": mp,
            "mp_id": mp_id,
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

@login_required
def pwa_maintenanceprotocol_entry(request, pk):
    wo = get_object_or_404(WorkOrder, pk=pk)

    # dostęp jak w API SR: assigned_to albo staff/superuser
    assigned_id = getattr(wo, "assigned_to_id", None)
    if not (request.user.is_superuser or request.user.is_staff or assigned_id == request.user.id):
        return HttpResponseForbidden("Not allowed")

    if wo.work_type != WorkOrder.WorkOrderType.MAINTENANCE:
        return HttpResponseForbidden("Protokół konserwacji tylko dla zleceń MAINTENANCE.")

    protocol = MaintenanceProtocol.objects.filter(work_order=wo).first()

    # jeśli jednak nie istnieje (stare zlecenia) — tworzymy jak w portalu
    if protocol is None:
        period_date = wo.planned_date or timezone.now().date()
        period_year = period_date.year
        period_month = period_date.month

        next_year = None
        next_month = None
        if wo.site and hasattr(wo.site, "get_next_maintenance_period"):
            next_year, next_month = wo.site.get_next_maintenance_period(
                from_year=period_year,
                from_month=period_month,
            )

        protocol = MaintenanceProtocol.objects.create(
            work_order=wo,
            site=wo.site,
            period_year=period_year,
            period_month=period_month,
            next_period_year=next_year,
            next_period_month=next_month,
        )

        if hasattr(protocol, "assign_number_if_needed"):
            protocol.assign_number_if_needed()
        if hasattr(protocol, "initialize_sections_from_previous_or_default"):
            protocol.initialize_sections_from_previous_or_default()

    back = request.GET.get("back", "")
    edit_url = reverse("core:pwa_maintenanceprotocol_edit", args=[protocol.pk])

    if back and url_has_allowed_host_and_scheme(
        back,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        edit_url = f"{edit_url}?back={back}"

    return redirect(edit_url)

@login_required
def pwa_maintenanceprotocol_edit(request, pk):
    protocol = get_object_or_404(
        MaintenanceProtocol.objects.select_related("site", "work_order"),
        pk=pk,
    )
    work_order = protocol.work_order
    site = protocol.site

    assigned_id = getattr(work_order, "assigned_to_id", None)
    if not (request.user.is_superuser or request.user.is_staff or assigned_id == request.user.id):
        return HttpResponseForbidden("Not allowed")

    sections_qs = protocol.sections.all().prefetch_related("check_items")

    back = request.GET.get("back", "")
    back_url = reverse("core:pwa_workorder_detail", args=[work_order.pk])

    if back and url_has_allowed_host_and_scheme(
        back,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        back_url = back

    if request.method == "POST":
        form = MaintenanceProtocolForm(request.POST, instance=protocol)

        section_formsets = []
        is_valid = form.is_valid()

        for section in sections_qs:
            formset = MaintenanceCheckItemFormSet(
                request.POST,
                queryset=section.check_items.all(),
                prefix=f"section-{section.pk}",
            )
            section_formsets.append({"section": section, "formset": formset})
            if not formset.is_valid():
                is_valid = False

        if is_valid:
            form.save()

            for bundle in section_formsets:
                section = bundle["section"]
                remarks_field = f"section_{section.pk}_remarks"
                new_remarks = (request.POST.get(remarks_field) or "").strip()

                if new_remarks != (section.section_remarks or ""):
                    section.section_remarks = new_remarks
                    section.save(update_fields=["section_remarks"])

                bundle["formset"].save()

            messages.success(request, "Zapisano protokół konserwacji.")
            return redirect(back_url)

    else:
        form = MaintenanceProtocolForm(instance=protocol)

        section_formsets = []
        for section in sections_qs:
            formset = MaintenanceCheckItemFormSet(
                queryset=section.check_items.all(),
                prefix=f"section-{section.pk}",
            )
            section_formsets.append({"section": section, "formset": formset})

    return render(
        request,
        "pwa/maintenance_protocol_form_pwa.html",
        {
            "protocol": protocol,
            "site": site,
            "work_order": work_order,
            "form": form,
            "section_formsets": section_formsets,
            "back_url": back_url,
        },
    )

@require_POST
@login_required
def api_pwa_maintenanceprotocol_save(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Bad JSON")

    mp_id = payload.get("mp_id")
    wo_id = payload.get("wo_id")
    fields = payload.get("fields") or {}

    if not mp_id or not isinstance(fields, dict):
        return HttpResponseBadRequest("Missing mp_id/fields")

    protocol = get_object_or_404(
        MaintenanceProtocol.objects.select_related("work_order", "site"),
        pk=mp_id,
    )

    if wo_id and protocol.work_order_id != int(wo_id):
        return HttpResponseBadRequest("WorkOrder mismatch")

    assigned_id = getattr(protocol.work_order, "assigned_to_id", None)
    if not (request.user.is_superuser or request.user.is_staff or assigned_id == request.user.id):
        return HttpResponseForbidden("Not allowed")

    # data: pola protokołu + formsety (extra klucze są OK — formy je ignorują)
    data = dict(fields)

    allowed = list(MaintenanceProtocolForm().fields.keys())
    base = model_to_dict(protocol, fields=allowed)
    for k in allowed:
        if k not in data:
            data[k] = base.get(k)

    form = MaintenanceProtocolForm(data=data, instance=protocol)

    sections_qs = protocol.sections.all().prefetch_related("check_items")
    bundles = []
    is_valid = form.is_valid()

    for section in sections_qs:
        fs = MaintenanceCheckItemFormSet(
            data=data,
            queryset=section.check_items.all(),
            prefix=f"section-{section.pk}",
        )
        bundles.append((section, fs))
        if not fs.is_valid():
            is_valid = False

    if not is_valid:
        return JsonResponse(
            {
                "ok": False,
                "form_errors": form.errors,
                "section_errors": [
                    {"section_id": s.pk, "errors": fs.errors, "non_form_errors": fs.non_form_errors()}
                    for (s, fs) in bundles
                    if (fs.errors or fs.non_form_errors())
                ],
            },
            status=400,
        )

    saved = form.save()

    for (section, fs) in bundles:
        remarks = (data.get(f"section_{section.pk}_remarks") or "").strip()
        if remarks != (section.section_remarks or ""):
            section.section_remarks = remarks
            section.save(update_fields=["section_remarks"])
        fs.save()

    updated_at = getattr(saved, "updated_at", None)
    return JsonResponse(
        {
            "ok": True,
            "mp_id": saved.pk,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }
    )

@require_POST
@login_required
def api_pwa_workorder_set_status(request, pk: int):
    wo = get_object_or_404(WorkOrder, pk=pk)

    # tylko biuro albo przypisany serwisant
    if not (is_office(request.user) or wo.assigned_to_id == request.user.id):
        return HttpResponseForbidden("Brak uprawnień")

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Niepoprawny JSON")

    new_status = payload.get("status")
    allowed = {WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.REALIZED}
    if new_status not in allowed:
        return HttpResponseBadRequest("Niedozwolony status")

    old_status = wo.status
    if old_status != new_status:
        wo.status = new_status
        wo.save(update_fields=["status", "updated_at"])

        # powiadomienie dla biura: gdy zmiana jest wykonana przez przypisanego serwisanta
        if request.user.id == wo.assigned_to_id:
            WorkOrderEvent.objects.create(
                work_order=wo,
                actor=request.user,
                kind=WorkOrderEvent.Kind.STATUS_CHANGE,
                old_status=old_status,
                new_status=new_status,
                source="PWA",
                is_read=False,
            )


    return JsonResponse({
        "id": wo.id,
        "status_code": wo.status,
        "status_label": wo.get_status_display(),
    })
