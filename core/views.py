from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse

from weasyprint import HTML

from .models import WorkOrder, Job, System, ServiceReport
from .forms import WorkOrderForm, ServiceReportForm



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
    """
    Edycja protokołu serwisowego na froncie (na razie tylko dla biura).
    """
    report = get_object_or_404(ServiceReport, pk=pk)

    # na tym etapie dajemy dostęp tylko biuru
    if not is_office(request.user):
        return HttpResponseForbidden("Brak uprawnień do edycji protokołu.")

    if request.method == "POST":
        finalize = "finalize" in request.POST  # kliknięto 'Zatwierdź i nadaj numer'

        form = ServiceReportForm(request.POST, instance=report)
        if form.is_valid():
            report = form.save(commit=False)

            if finalize:
                report.status = ServiceReport.Status.FINAL

            report.save()
            # po zapisie wracamy do szczegółów zlecenia
            return redirect("core:workorder_detail", pk=report.work_order.pk)
    else:
        form = ServiceReportForm(instance=report)

    context = {
        "form": form,
        "report": report,
        "order": report.work_order,
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
        report = ServiceReport.objects.create(work_order=order)

    # teraz zamiast admina -> nasz front
    return redirect("core:service_report_edit", pk=report.pk)

@login_required
def service_report_pdf(request, pk):
    report = get_object_or_404(ServiceReport, pk=pk)
    order = report.work_order

    logo_path = request.build_absolute_uri('/static/img/logo2-150.jpg')

    html = render_to_string(
        "core/servicereport_pdf.html",
        {
            "report": report,
            "order": order,
            "logo_path": logo_path,
        },
        request=request,
    )

    pdf_file = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    filename = (report.number or f"protokol_{report.pk}") + ".pdf"
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response