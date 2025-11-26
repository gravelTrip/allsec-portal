from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.core.paginator import Paginator


from .models import WorkOrder, Job

# Create your views here.
from django.shortcuts import render
from django.utils import timezone

from .models import WorkOrder, Job


def dashboard(request):
    today = timezone.localdate()

    # statystyki do kafelków
    try:
        open_orders = WorkOrder.objects.exclude(
            status=WorkOrder.Status.COMPLETED
        ).count()
    except AttributeError:
        open_orders = WorkOrder.objects.count()

    try:
        critical_orders = WorkOrder.objects.filter(
            priority=getattr(WorkOrder.Priority, "CRITICAL", None)
        ).exclude(
            status=getattr(WorkOrder.Status, "COMPLETED", None)
        ).count()
    except AttributeError:
        critical_orders = 0

    try:
        overdue_maintenance = WorkOrder.objects.filter(
            work_type=WorkOrder.WorkOrderType.MAINTENANCE,
            planned_date__lt=today,
        ).exclude(
            status=WorkOrder.Status.COMPLETED
        ).count()
    except AttributeError:
        overdue_maintenance = 0

    try:
        jobs_in_progress = Job.objects.exclude(
            status=getattr(Job.Status, "COMPLETED", None)
        ).count()
    except AttributeError:
        jobs_in_progress = Job.objects.count()

    # ZLECENIA NA DZIŚ (na razie: planowana data = dziś)
    today_orders = (
        WorkOrder.objects.filter(planned_date=today)
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

def workorder_list(request):
    orders_qs = (
        WorkOrder.objects.all()
        .select_related("site")
        .order_by("-planned_date", "-updated_at")
    )

    # wartości z query stringa, np. ?work_type=SERVICE&status=NEW
    filter_work_type = request.GET.get("work_type", "")
    filter_status = request.GET.get("status", "")

    # filtr po typie zlecenia
    if filter_work_type:
        try:
            if filter_work_type in WorkOrder.WorkOrderType.values:
                orders_qs = orders_qs.filter(work_type=filter_work_type)
        except AttributeError:
            # jeśli enum inaczej się nazywa, filtrujemy "na dziko"
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

    # proste listy wyboru do selectów
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
    }
    return render(request, "core/workorder_list.html", context)

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
