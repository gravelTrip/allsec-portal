from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse

from .models import WorkOrder, Job, System
from .forms import WorkOrderForm


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

    # statystyki do kafelków (na bazie base_qs)
    try:
        open_orders = base_qs.exclude(
            status=WorkOrder.Status.COMPLETED
        ).count()
    except AttributeError:
        open_orders = base_qs.count()

    try:
        critical_orders = base_qs.filter(
            priority=getattr(WorkOrder.Priority, "CRITICAL", None)
        ).exclude(
            status=getattr(WorkOrder.Status, "COMPLETED", None)
        ).count()
    except AttributeError:
        critical_orders = 0

    try:
        overdue_maintenance = base_qs.filter(
            work_type=WorkOrder.WorkOrderType.MAINTENANCE,
            planned_date__lt=today,
        ).exclude(
            status=WorkOrder.Status.COMPLETED
        ).count()
    except AttributeError:
        overdue_maintenance = 0

    # roboty na razie liczymy globalnie (później możemy zawęzić)
    try:
        jobs_in_progress = Job.objects.exclude(
            status=getattr(Job.Status, "COMPLETED", None)
        ).count()
    except AttributeError:
        jobs_in_progress = Job.objects.count()

    # ZLECENIA NA DZIŚ – też na bazie base_qs
    today_orders = (
        base_qs.filter(planned_date=today)
        .order_by("planned_date", "priority")
        .select_related("site")
    )

    context = {
        "stats": {
            "open_orders": open_orders,
            "critical_orders": critical_orders,
            "overdue_maintenance": overdue_maintenance,
            "jobs_in_progress": jobs_in_progress,
        },
        "today_orders": today_orders,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def workorder_list(request):
    user = request.user

    orders_qs = (
        WorkOrder.objects.all()
        .select_related("site")
        .order_by("-planned_date", "-updated_at")
    )

    # jeśli serwisant (i nie biuro) -> tylko jego zlecenia
    if is_technician(user) and not is_office(user):
        orders_qs = orders_qs.filter(assigned_to=user)

    # wartości z query stringa, np. ?work_type=SERVICE&status=NEW
    filter_work_type = request.GET.get("work_type", "")
    filter_status = request.GET.get("status", "")

    # filtr po typie zlecenia
    if filter_work_type:
        try:
            if filter_work_type in WorkOrder.WorkOrderType.values:
                orders_qs = orders_qs.filter(work_type=filter_work_type)
        except AttributeError:
            orders_qs = orders_qs.filter(work_type=filter_work_type)

    # filtr po statusie
    if filter_status:
        try:
            if filter_status in WorkOrder.Status.values:
                orders_qs = orders_qs.filter(status=filter_status)
        except AttributeError:
            orders_qs = orders_qs.filter(status=filter_status)

    # paginacja
    page_number = request.GET.get("page")
    paginator = Paginator(orders_qs, 25)
    page_obj = paginator.get_page(page_number)

    # listy do selectów
    work_type_choices = []
    try:
        work_type_choices = [
            ("", "Typ: wszystkie"),
            (WorkOrder.WorkOrderType.SERVICE, "Serwis"),
            (WorkOrder.WorkOrderType.MAINTENANCE, "Przegląd"),
            (WorkOrder.WorkOrderType.JOB, "Robota"),
        ]
    except AttributeError:
        work_type_choices = [("", "Typ: wszystkie")]

    status_choices = []
    try:
        status_choices = [
            ("", "Status: wszystkie"),
            (WorkOrder.Status.NEW, "Nowe"),
            (WorkOrder.Status.IN_PROGRESS, "W realizacji"),
            (WorkOrder.Status.COMPLETED, "Zamknięte"),
        ]
    except AttributeError:
        status_choices = [("", "Status: wszystkie")]

    context = {
        "orders": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "filter_work_type": filter_work_type,
        "filter_status": filter_status,
        "work_type_choices": work_type_choices,
        "status_choices": status_choices,
        "can_create": is_office(user),
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

    context = {
        "order": order,
        "service_report": service_report,
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
