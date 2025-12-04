from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.db.models import Sum

import base64
from weasyprint import HTML
from pathlib import Path
from django.conf import settings

from .models import (
    WorkOrder,
    Job,
    System,
    ServiceReport,
    Site,
    Manager,
    Contact,
    SiteContact,
    Entity,
)

from .forms import (
    WorkOrderForm,
    ServiceReportForm,
    SiteForm,
    ManagerForm,
    ContactForm,
    SystemForm,
    SiteContactForm,
    ServiceReportItemFormSet,
    EntityForm,
)



# Create your views here.
def is_office(user):
    """Użytkownik biura: pełne prawa.
    - superuser
    - lub należy do grupy 'office'
    """
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name="office").exists()


def is_technician(user):
    """Serwisant: ograniczony widok.
    - należy do grupy 'technician'
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name="technician").exists()


@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()

    # BAZOWA QUERYSET ZLECEŃ:
    # - biuro: wszystkie zlecenia
    # - serwisant: tylko przypisane do niego
    base_qs = WorkOrder.objects.all()
    if is_technician(user) and not is_office(user):
        base_qs = base_qs.filter(assigned_to=user)

    # 1) Otwarte zlecenia (wszystko poza zakończonymi)
    open_orders = base_qs.exclude(status=WorkOrder.Status.COMPLETED).count()

    # 2) "Krytyczne" – teraz rozumiemy jako oczekujące na decyzję klienta lub materiał
    critical_orders = base_qs.filter(
        status__in=[
            WorkOrder.Status.WAITING_FOR_DECISION,
            WorkOrder.Status.WAITING_FOR_PARTS,
        ]
    ).count()

    # 3) Przeterminowane przeglądy (MAINTENANCE z terminem w przeszłości, nie zakończone)
    overdue_maintenance = base_qs.filter(
        work_type=WorkOrder.WorkOrderType.MAINTENANCE,
        planned_date__lt=today,
    ).exclude(
        status=WorkOrder.Status.COMPLETED
    ).count()

    # 4) Roboty w toku (wszystko poza zakończonymi)
    try:
        jobs_in_progress = Job.objects.exclude(status=Job.Status.COMPLETED).count()
    except AttributeError:
        # gdyby Job.Status jeszcze nie miał COMPLETED, pokaż po prostu liczbę robót
        jobs_in_progress = Job.objects.count()

    # ZLECENIA NA DZIŚ – posortowane po dacie i dacie utworzenia (bez priority)
    today_orders = (
        base_qs.filter(planned_date=today)
        .order_by("planned_date", "created_at")
        .select_related("site")
    )

    context = {
        "stats": {
            "open_orders": open_orders,
            "critical_orders": critical_orders,          # teraz: czekające na decyzję / materiał
            "overdue_maintenance": overdue_maintenance,
            "jobs_in_progress": jobs_in_progress,
        },
        "today_orders": today_orders,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def workorder_list(request):
    qs = (
        WorkOrder.objects
        .select_related("site", "assigned_to")
        .prefetch_related("systems")
        .order_by("-created_at")  # albo inne sortowanie, które już masz
    )

    # wartości z filtrów (z formularza w template)
    filter_work_type = request.GET.get("work_type", "")
    filter_status = request.GET.get("status", "")
    show_closed = request.GET.get("show_closed") == "on"

    if filter_work_type:
        qs = qs.filter(work_type=filter_work_type)

    if filter_status:
        # jeśli użytkownik wybrał konkretny status, pokazujemy dokładnie ten
        qs = qs.filter(status=filter_status)
    else:
        # jeśli NIE wybrano konkretnego statusu i checkbox nie zaznaczony,
        # ukrywamy Zakończone i Odwołane
        if not show_closed:
            qs = qs.exclude(
                status__in=[WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED]
            )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    work_type_choices = [("", "Typ: wszystkie")] + list(WorkOrder.WorkOrderType.choices)
    status_choices = [("", "Status: wszystkie")] + list(WorkOrder.Status.choices)

    context = {
        "orders": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "work_type_choices": work_type_choices,
        "status_choices": status_choices,
        "filter_work_type": filter_work_type,
        "filter_status": filter_status,
        "show_closed": show_closed,
        "can_create": is_office(request.user),
    }
    return render(request, "core/workorder_list.html", context)


@login_required
def service_report_list(request):
    qs = (
        ServiceReport.objects
        .select_related("work_order__site", "work_order")
        .order_by("-report_date", "-id")
    )

    status = request.GET.get("status", "")
    only_final = request.GET.get("only_final") == "on"

    if status:
        qs = qs.filter(status=status)
    if only_final:
        qs = qs.filter(status=ServiceReport.Status.FINAL)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "filter_status": status,
        "only_final": only_final,
        "status_choices": ServiceReport.Status.choices,
    }
    return render(request, "core/servicereport_list.html", context)


@login_required
def workorder_detail(request, pk):
    order = get_object_or_404(
        WorkOrder.objects.select_related("site", "assigned_to", "job").prefetch_related("systems"),
        pk=pk,
    )

    # spróbujemy wyciągnąć powiązany protokół serwisowy (jeśli istnieje)
    service_report = getattr(order, "service_report", None)

    can_edit = is_office(request.user)

    context = {
        "order": order,
        "service_report": service_report,
        "can_edit": can_edit,
    }
    return render(request, "core/workorder_detail.html", context)


@login_required
def workorder_create(request):
    # tylko biuro może dodawać zlecenia
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do dodawania zleceń.")

    if request.method == "POST":
        form = WorkOrderForm(request.POST)
        if form.is_valid():
            order = form.save()
            return redirect("core:workorder_detail", pk=order.pk)
    else:
        form = WorkOrderForm()

    context = {
        "form": form,
        "is_edit": False,
        "order": None,
    }
    return render(request, "core/workorder_form.html", context)

@login_required
def workorder_edit(request, pk):
    order = get_object_or_404(WorkOrder, pk=pk)

    # tylko biuro może edytować zlecenia
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji zlecenia.")

    if request.method == "POST":
        form = WorkOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            return redirect("core:workorder_detail", pk=order.pk)
    else:
        form = WorkOrderForm(instance=order)

    context = {
        "form": form,
        "is_edit": True,
        "order": order,
    }
    return render(request, "core/workorder_form.html", context)

# =========================
# OBIEKTY (Site)
# =========================
@login_required
def site_list(request):
    qs = Site.objects.select_related("entity", "manager").order_by("name")
    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "sites": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "can_create": is_office(request.user),
    }
    return render(request, "core/site_list.html", context)


@login_required
def site_detail(request, pk):
    site = get_object_or_404(
        Site.objects.select_related("entity", "manager").prefetch_related(
            "systems", "site_contacts__contact"
        ),
        pk=pk,
    )

    systems = site.systems.all().order_by("system_type", "name")
    site_contacts = site.site_contacts.select_related("contact").all().order_by("role")

    context = {
        "site": site,
        "systems": systems,
        "site_contacts": site_contacts,
        "can_edit": is_office(request.user),
    }
    return render(request, "core/site_detail.html", context)

@login_required
def system_create_for_site(request, site_pk):
    site = get_object_or_404(Site, pk=site_pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do dodawania systemów.")

    if request.method == "POST":
        form = SystemForm(request.POST)
        if form.is_valid():
            system = form.save(commit=False)
            system.site = site
            system.save()
            return redirect("core:site_detail", pk=site.pk)
    else:
        form = SystemForm()

    context = {
        "form": form,
        "site": site,
        "system": None,
    }
    return render(request, "core/system_form.html", context)


@login_required
def system_detail(request, pk):
    system = get_object_or_404(
        System.objects.select_related("site"), pk=pk
    )

    # Używamy formularza tylko po to, żeby mieć listę pól + etykiety
    form = SystemForm(instance=system)

    context = {
        "system": system,
        "site": system.site,
        "can_edit": is_office(request.user),
        "form": form,
    }
    return render(request, "core/system_detail.html", context)


@login_required
def system_edit(request, pk):
    system = get_object_or_404(System, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji systemów.")

    if request.method == "POST":
        form = SystemForm(request.POST, instance=system)
        if form.is_valid():
            form.save()
            return redirect("core:site_detail", pk=system.site.pk)
    else:
        form = SystemForm(instance=system)

    context = {
        "form": form,
        "system": system,
        "site": system.site,
    }
    return render(request, "core/system_form.html", context)


@login_required
def system_delete(request, pk):
    system = get_object_or_404(System, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do usuwania systemów.")

    site_pk = system.site.pk

    if request.method == "POST":
        system.delete()
        return redirect("core:site_detail", pk=site_pk)

    # Przy GET wracamy do szczegółów systemu – można też od razu do obiektu
    return redirect("core:system_detail", pk=pk)


@login_required
def sitecontact_create(request, site_pk):
    site = get_object_or_404(Site, pk=site_pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do dodawania powiązań kontaktów.")

    if request.method == "POST":
        form = SiteContactForm(request.POST)
        if form.is_valid():
            sc = form.save(commit=False)
            sc.site = site
            sc.save()
            return redirect("core:site_detail", pk=site.pk)
    else:
        form = SiteContactForm()

    context = {
        "form": form,
        "site": site,
        "sitecontact": None,
    }
    return render(request, "core/sitecontact_form.html", context)


@login_required
def sitecontact_detail(request, pk):
    sc = get_object_or_404(
        SiteContact.objects.select_related("site", "contact"), pk=pk
    )

    context = {
        "sitecontact": sc,
        "site": sc.site,
        "contact": sc.contact,
        "can_edit": is_office(request.user),
    }
    return render(request, "core/sitecontact_detail.html", context)


@login_required
def sitecontact_edit(request, pk):
    sc = get_object_or_404(SiteContact, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji powiązania kontaktu.")

    if request.method == "POST":
        form = SiteContactForm(request.POST, instance=sc)
        if form.is_valid():
            form.save()
            return redirect("core:site_detail", pk=sc.site.pk)
    else:
        form = SiteContactForm(instance=sc)

    context = {
        "form": form,
        "sitecontact": sc,
        "site": sc.site,
        "contact": sc.contact,
    }
    return render(request, "core/sitecontact_form.html", context)


@login_required
def sitecontact_delete(request, pk):
    sc = get_object_or_404(SiteContact, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do usuwania powiązania kontaktu.")

    site_pk = sc.site.pk

    if request.method == "POST":
        sc.delete()
        return redirect("core:site_detail", pk=site_pk)

    return redirect("core:sitecontact_detail", pk=pk)


@login_required
def site_create(request):
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do tworzenia obiektów.")

    if request.method == "POST":
        form = SiteForm(request.POST)
        if form.is_valid():
            site = form.save()
            return redirect("core:site_detail", pk=site.pk)
    else:
        form = SiteForm()

    context = {
        "form": form,
        "site": None,
    }
    return render(request, "core/site_form.html", context)


@login_required
def site_edit(request, pk):
    site = get_object_or_404(Site, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji obiektu.")

    if request.method == "POST":
        form = SiteForm(request.POST, instance=site)

        if form.is_valid():
            form.save()
            return redirect("core:site_detail", pk=site.pk)
    else:
        form = SiteForm(instance=site)
    context = {
        "form": form,
        "site": site,
        "is_edit": True,
    }
    return render(request, "core/site_form.html", context)


@login_required
def site_delete(request, pk):
    site = get_object_or_404(Site, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do usuwania obiektu.")

    if request.method == "POST":
        site.delete()
        return redirect("core:site_list")

    # jeśli GET – wróć do szczegółów
    return redirect("core:site_detail", pk=pk)


# =========================
# ZARZĄDCY (Manager)
# =========================
@login_required
def manager_list(request):
    qs = Manager.objects.order_by("short_name", "full_name")
    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "managers": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "can_create": is_office(request.user),
    }
    return render(request, "core/manager_list.html", context)


@login_required
def manager_detail(request, pk):
    manager = get_object_or_404(
        Manager.objects.prefetch_related("sites", "contacts"),
        pk=pk,
    )

    context = {
        "manager": manager,
        "sites": manager.sites.all().order_by("name"),
        "contacts": manager.contacts.all().order_by("last_name", "first_name"),
        "can_edit": is_office(request.user),
    }
    return render(request, "core/manager_detail.html", context)


@login_required
def manager_create(request):
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do tworzenia zarządców.")

    if request.method == "POST":
        form = ManagerForm(request.POST)
        if form.is_valid():
            manager = form.save()
            return redirect("core:manager_detail", pk=manager.pk)
    else:
        form = ManagerForm()

    context = {
        "form": form,
        "manager": None,
    }
    return render(request, "core/manager_form.html", context)


@login_required
def manager_edit(request, pk):
    manager = get_object_or_404(Manager, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji zarządcy.")

    if request.method == "POST":
        form = ManagerForm(request.POST, instance=manager)
        if form.is_valid():
            manager = form.save()
            return redirect("core:manager_detail", pk=manager.pk)
    else:
        form = ManagerForm(instance=manager)

    context = {
        "form": form,
        "manager": manager,
    }
    return render(request, "core/manager_form.html", context)


@login_required
def manager_delete(request, pk):
    manager = get_object_or_404(Manager, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do usuwania zarządcy.")

    if request.method == "POST":
        manager.delete()
        return redirect("core:manager_list")

    return redirect("core:manager_detail", pk=pk)


# =========================
# KONTAKTY (Contact)
# =========================
@login_required
def contact_list(request):
    qs = Contact.objects.select_related("manager").order_by("last_name", "first_name")
    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "contacts": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "can_create": is_office(request.user),
    }
    return render(request, "core/contact_list.html", context)


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(
        Contact.objects.select_related("manager").prefetch_related(
            "site_links__site"
        ),
        pk=pk,
    )

    site_links = contact.site_links.select_related("site").all()

    context = {
        "contact": contact,
        "site_links": site_links,
        "can_edit": is_office(request.user),
    }
    return render(request, "core/contact_detail.html", context)


@login_required
def contact_create(request):
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do tworzenia kontaktów.")

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            return redirect("core:contact_detail", pk=contact.pk)
    else:
        form = ContactForm()

    context = {
        "form": form,
        "contact": None,
    }
    return render(request, "core/contact_form.html", context)


@login_required
def contact_edit(request, pk):
    contact = get_object_or_404(Contact, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji kontaktu.")

    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            contact = form.save()
            return redirect("core:contact_detail", pk=contact.pk)
    else:
        form = ContactForm(instance=contact)

    context = {
        "form": form,
        "contact": contact,
    }
    return render(request, "core/contact_form.html", context)


@login_required
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do usuwania kontaktu.")

    if request.method == "POST":
        contact.delete()
        return redirect("core:contact_list")

    return redirect("core:contact_detail", pk=pk)

@login_required
def ajax_site_systems(request, site_id):
    # dostęp: biuro + (w przyszłości) serwisanci
    if not (is_office(request.user) or is_technician(request.user)):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    systems = (
        System.objects.filter(site_id=site_id)
        .order_by("system_type", "manufacturer", "model")
    )

    data = []
    for s in systems:
        parts = [s.get_system_type_display()]
        if s.manufacturer:
            parts.append(str(s.manufacturer))
        if s.model:
            parts.append(str(s.model))
        label = " – ".join(parts)
        if getattr(s, "in_contract", False):
            label += " (w umowie)"

        data.append(
            {
                "id": s.id,
                "label": label,
            }
        )

    return JsonResponse({"systems": data})

@login_required
def service_report_edit(request, pk):
    report = get_object_or_404(
        ServiceReport.objects.select_related("work_order__site"), pk=pk
    )
    order = report.work_order
    site = order.site if order else None

    if request.method == "POST":
        form = ServiceReportForm(request.POST, instance=report)
        item_formset = ServiceReportItemFormSet(request.POST, instance=report)

        if form.is_valid() and item_formset.is_valid():
            # Czy kliknięto zielony przycisk "Zatwierdź i nadaj numer"
            finalize = "finalize" in request.POST

            # Chcemy mieć kontrolę nad statusem, więc commit=False
            report_obj = form.save(commit=False)

            if finalize:
                report_obj.status = ServiceReport.Status.FINAL
            # jeśli nie finalize – zostawiamy status taki, jak był (np. DRAFT)

            # to wywoła logikę w modelu (data protokołu + automatyczny numer)
            report_obj.save()

            # upewniamy się, że formset zapisuje się do tego samego protokołu
            item_formset.instance = report_obj
            item_formset.save()

            return redirect("core:service_report_detail", pk=report_obj.pk)
    else:
        form = ServiceReportForm(instance=report)
        item_formset = ServiceReportItemFormSet(instance=report)

    items_total = report.items.aggregate(total=Sum("total_price"))["total"] or 0

    context = {
        "report": report,
        "order": order,
        "site": site,
        "form": form,
        "item_formset": item_formset,
        "items_total": items_total,
    }
    return render(request, "core/servicereport_form.html", context)


@login_required
def service_report_entry(request, pk):
    """
    Wejście do protokołu z poziomu zlecenia:
    - jeśli protokół istnieje -> otwórz go na froncie,
    - jeśli nie -> utwórz pusty (szkic) i potem otwórz.
    """
    order = get_object_or_404(WorkOrder, pk=pk)

    # biuro + (docelowo) serwisanci
    if not (is_office(request.user) or is_technician(request.user)):
        return HttpResponseForbidden("Brak uprawnień do pracy z protokołem.")

    # Na razie pilnujemy, że protokół tylko do zleceń typu SERWIS
    if order.work_type != WorkOrder.WorkOrderType.SERVICE:
        return HttpResponseForbidden("Protokół serwisowy dostępny tylko dla zleceń serwisowych.")

    # szukamy istniejącego protokołu
    report = ServiceReport.objects.filter(work_order=order).first()

    # jeśli nie ma -> tworzymy nowy (status / numer ogarnia model)
    if report is None:
        tech_name = ""
        if order.assigned_to:
            user = order.assigned_to
            tech_name = (
                getattr(user, "get_full_name", lambda: "")()
                or getattr(user, "username", "")
            )

        report = ServiceReport.objects.create(
            work_order=order,
            notes_internal=order.internal_notes or "",
            technicians=tech_name,
        )

    # teraz zamiast admina -> nasz front
    return redirect("core:service_report_detail", pk=report.pk)

def service_report_detail(request, pk):
    report = get_object_or_404(
        ServiceReport.objects.select_related("work_order__site", "work_order"),
        pk=pk,
    )
    order = report.work_order
    site = order.site if order else None

    # wszystkie pozycje + suma netto
    items = report.items.all()
    items_total = items.aggregate(total=Sum("total_price"))["total"] or 0

    context = {
        "report": report,
        "order": order,
        "site": site,
        "items": items,
        "items_total": items_total,
        # Edytować mogą biuro + serwisanci (jak przy wejściu przez zlecenie)
        "can_edit": is_office(request.user) or is_technician(request.user),
    }
    return render(request, "core/servicereport_detail.html", context)

def get_logo_data_uri():
    """Zwraca data URL z logo jako base64, albo None jeśli się nie uda."""
    logo_path = Path(settings.BASE_DIR, "static", "img", "logo2-150.jpg")
    try:
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except OSError:
        return None

@login_required
def service_report_pdf(request, pk):
    report = get_object_or_404(ServiceReport, pk=pk)
    order = report.work_order

     # wszystkie pozycje + suma netto
    items = report.items.all()
    items_total = items.aggregate(total=Sum("total_price"))["total"] or 0

    logo_data_uri = get_logo_data_uri()

    html = render_to_string(
        "core/servicereport_pdf.html",
        {
            "report": report,
            "order": order,
            "logo_path": logo_data_uri,
            "items": items,
            "items_total": items_total,
        },
        request=request,
    )

    pdf_file = HTML(
        string=html,
        # base_url też ustawiamy na katalog projektu, wtedy relative URL-e
        # będą liczone względem tego katalogu
        base_url=settings.BASE_DIR.as_uri(),
    ).write_pdf()

    filename = (report.number or f"protokol_{report.pk}") + ".pdf"
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

# =========================
# DANE FAKTUROWE (Entity)
# =========================

@login_required
def entity_list(request):
    qs = Entity.objects.order_by("name")
    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "entities": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "can_create": is_office(request.user),
    }
    return render(request, "core/entity_list.html", context)


@login_required
def entity_detail(request, pk):
    entity = get_object_or_404(Entity, pk=pk)
    sites = entity.sites.select_related("manager").order_by("name")

    context = {
        "entity": entity,
        "sites": sites,
    }
    return render(request, "core/entity_detail.html", context)


@login_required
def entity_create(request):
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do tworzenia danych FV.")

    if request.method == "POST":
        form = EntityForm(request.POST)
        if form.is_valid():
            entity = form.save()
            return redirect("core:entity_detail", pk=entity.pk)
    else:
        form = EntityForm()

    context = {
        "form": form,
        "entity": None,
    }
    return render(request, "core/entity_form.html", context)


@login_required
def entity_edit(request, pk):
    entity = get_object_or_404(Entity, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji danych FV.")

    if request.method == "POST":
        form = EntityForm(request.POST, instance=entity)
        if form.is_valid():
            entity = form.save()
            return redirect("core:entity_detail", pk=entity.pk)
    else:
        form = EntityForm(instance=entity)

    context = {
        "form": form,
        "entity": entity,
    }
    return render(request, "core/entity_form.html", context)


@login_required
def entity_delete(request, pk):
    entity = get_object_or_404(Entity, pk=pk)

    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do usuwania danych FV.")

    if request.method == "POST":
        entity.delete()
        return redirect("core:entity_list")

    return redirect("core:entity_detail", pk=pk)

@login_required
def site_contacts_json(request, site_id):
    """
    Zwraca kontakty powiązane z danym obiektem (Site) w formacie pod Tom Select.
    """
    site = get_object_or_404(Site, pk=site_id)

    site_contacts = (
        SiteContact.objects
        .filter(site=site)
        .select_related("contact")
    )

    # Unikalne kontakty
    contacts_by_id = {}
    for sc in site_contacts:
        contact = sc.contact
        if contact and contact.pk not in contacts_by_id:
            contacts_by_id[contact.pk] = contact

    # Uporządkuj po __str__ (czyli tak jak pokazujesz kontakty w innych miejscach)
    contacts = sorted(contacts_by_id.values(), key=lambda c: str(c))

    results = [
        {
            "value": contact.pk,
            "text": str(contact),
        }
        for contact in contacts
    ]

    return JsonResponse({"results": results})
