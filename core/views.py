from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, timedelta
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Sum

from django.views.decorators.clickjacking import xframe_options_sameorigin


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
    MaintenanceProtocol,
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
    MaintenanceProtocolForm,
    MaintenanceCheckItemFormSet,
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

    # --- FILTRY LISTY "Zlecenia" ---

    orders = base_qs.select_related("site", "assigned_to")

    # Typ zlecenia
    type_param = request.GET.get("type", "").strip()
    valid_work_types = {choice[0] for choice in WorkOrder.WorkOrderType.choices}
    if type_param and type_param in valid_work_types:
        orders = orders.filter(work_type=type_param)

    # Serwisant
    assignee_param = request.GET.get("assignee", "").strip()
    if assignee_param:
        try:
            assignee_id = int(assignee_param)
            orders = orders.filter(assigned_to_id=assignee_id)
        except (TypeError, ValueError):
            pass

    # Status
    status_param = request.GET.get("status", "").strip()
    valid_statuses = {choice[0] for choice in WorkOrder.Status.choices}
    if status_param and status_param in valid_statuses:
        orders = orders.filter(status=status_param)

    # Czas
    time_param = request.GET.get("time", "week").strip()  # domyślnie tydzień
    date_from_str = request.GET.get("date_from", "").strip()
    date_to_str = request.GET.get("date_to", "").strip()

    if time_param == "week":
        # poniedziałek–niedziela bieżącego tygodnia
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        orders = orders.filter(planned_date__range=(start_of_week, end_of_week))
    elif time_param == "month":
        orders = orders.filter(
            planned_date__year=today.year,
            planned_date__month=today.month,
        )
    elif time_param == "year":
        orders = orders.filter(planned_date__year=today.year)
    elif time_param == "range":
        try:
            if date_from_str:
                df = date.fromisoformat(date_from_str)
            else:
                df = None
            if date_to_str:
                dt = date.fromisoformat(date_to_str)
            else:
                dt = None
            if df and dt:
                orders = orders.filter(planned_date__range=(df, dt))
            elif df:
                orders = orders.filter(planned_date__gte=df)
            elif dt:
                orders = orders.filter(planned_date__lte=dt)
        except ValueError:
            # jak coś nie tak z datą, ignorujemy filtr zakresu
            pass
    # "all" → bez filtra daty

    # Checkbox "Ukryj zakończone":
    # - jeśli NIE ma żadnych filtrów w URL -> domyślnie ukrywamy zakończone
    # - jeśli są jakieś filtry -> respektujemy parametr hide_completed (obecny/nieobecny)
    filter_keys = ["type", "assignee", "status", "time", "date_from", "date_to", "hide_completed"]
    has_filter_params = any(key in request.GET for key in filter_keys)

    if has_filter_params:
        hide_completed_param = request.GET.get("hide_completed", "")
        hide_completed = hide_completed_param in ("1", "true", "on", "yes")
    else:
        hide_completed = True

    if hide_completed:
        orders = orders.exclude(status=WorkOrder.Status.COMPLETED)

    # Sortowanie – na koniec po dacie i dacie utworzenia
    orders = orders.order_by("planned_date", "created_at")

    # Dane do dropdownów filtrów
    User = get_user_model()
    assignee_qs = (
        User.objects.filter(assigned_work_orders__isnull=False)
        .distinct()
        .order_by("first_name", "last_name", "username")
    )

    # Listy opcji z informacją, który element jest zaznaczony
    type_choices = [
        {
            "value": value,
            "label": label,
            "selected": (value == type_param),
        }
        for value, label in WorkOrder.WorkOrderType.choices
    ]

    status_choices = [
        {
            "value": value,
            "label": label,
            "selected": (value == status_param),
        }
        for value, label in WorkOrder.Status.choices
    ]

    time_raw_choices = [
        ("all", "Wszystko"),
        ("week", "Tydzień"),
        ("month", "Miesiąc"),
        ("year", "Rok"),
        ("range", "Zakres"),
    ]
    time_choices = [
        {
            "value": value,
            "label": label,
            "selected": (value == time_param),
        }
        for value, label in time_raw_choices
    ]

    assignee_choices = [
        {
            "id": u.id,
            "label": u.get_full_name() or u.username,
            "selected": (str(u.id) == assignee_param),
        }
        for u in assignee_qs
    ]



    # --- MODUŁ "Konserwacje na:" ---

    def add_months(year: int, month: int, delta: int):
        """
        Przesunięcie (rok, miesiąc) o delta miesięcy (może być ujemne).
        """
        total = year * 12 + (month - 1) + delta
        new_year = total // 12
        new_month = (total % 12) + 1
        return new_year, new_month

    try:
        month_offset = int(request.GET.get("km", "0"))
    except ValueError:
        month_offset = 0
    # zakres -1..3 jak ustaliliśmy
    month_offset = max(-1, min(3, month_offset))

    base_year, base_month = today.year, today.month
    selected_year, selected_month = add_months(base_year, base_month, month_offset)

    # Lista miesięcy: -1..3 względem bieżącego
    month_choices = []
    for delta in range(-1, 4):  # -1, 0, 1, 2, 3
        y, m = add_months(base_year, base_month, delta)
        month_choices.append(
            {
                "label": f"{m:02d}/{y}",
                "value": delta,
                "is_current": delta == month_offset,
            }
        )

    # Obiekty z konserwacjami wg ustawień obiektu
    sites_qs = Site.objects.exclude(
        maintenance_frequency=Site.MaintenanceFrequency.NONE
    ).select_related("entity")

    maintenance_items = []

    for site in sites_qs:
        # Miesiące wykonania konserwacji:
        # - preferujemy execution_months (jeśli używasz), fallback do maintenance_months
        exec_months = []
        try:
            if site.execution_months:
                exec_months = [int(x) for x in site.execution_months]
        except (TypeError, ValueError):
            exec_months = []

        if not exec_months:
            exec_months = site.maintenance_months

        if selected_month not in exec_months:
            continue

        # Zlecenia konserwacji na ten okres
        period_orders = WorkOrder.objects.filter(
            site=site,
            work_type=WorkOrder.WorkOrderType.MAINTENANCE,
            planned_date__year=selected_year,
            planned_date__month=selected_month,
        )

        # Jeśli jest zlecenie ZAKOŃCZONE → obiekt znika z listy
        if period_orders.filter(status=WorkOrder.Status.COMPLETED).exists():
            continue

        # Jeśli jest zlecenie w innym statusie → pokażemy "W trakcie"
        ongoing_order = (
            period_orders.exclude(status=WorkOrder.Status.COMPLETED)
            .order_by("planned_date", "created_at")
            .first()
        )

        maintenance_items.append(
            {
                "site": site,
                "ongoing_order": ongoing_order,  # None → pokaż "Utwórz"
            }
        )

    # Sortowanie: entity.name, site.name
    maintenance_items.sort(
        key=lambda item: (
            item["site"].entity.name if item["site"].entity_id else "",
            item["site"].name,
        )
    )

    maintenance_module = {
        "selected_year": selected_year,
        "selected_month": selected_month,
        "selected_label": f"{selected_month:02d}/{selected_year}",
        "selected_period_param": f"{selected_year}-{selected_month:02d}",  # np. 2025-12
        "month_offset": month_offset,
        "month_choices": month_choices,
        "items": maintenance_items,
    }


    context = {
        "stats": {
            "open_orders": open_orders,
            "critical_orders": critical_orders,
            "overdue_maintenance": overdue_maintenance,
            "jobs_in_progress": jobs_in_progress,
        },
        "today_orders": orders,  # to już jest przefiltrowana lista "Zleceń"
        "maintenance_module": maintenance_module,
        "order_filters": {
            "type": type_param,
            "status": status_param,
            "assignee": assignee_param,
            "time": time_param,
            "date_from": date_from_str,
            "date_to": date_to_str,
            "hide_completed": hide_completed,
            "type_choices": type_choices,
            "status_choices": status_choices,
            "assignee_choices": assignee_choices,
            "time_choices": time_choices,
        },
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
def maintenance_protocol_list(request):
    qs = (
        MaintenanceProtocol.objects
        .select_related("site", "work_order")
        .order_by("-period_year", "-period_month", "-id")
    )

    status = request.GET.get("status", "")
    only_final = request.GET.get("only_final") == "on"

    if status:
        qs = qs.filter(status=status)
    if only_final:
        try:
            qs = qs.filter(status=MaintenanceProtocol.Status.FINAL)
        except AttributeError:
            # jeśli kiedyś zrezygnujesz z pól statusowych, to po prostu nic nie filtrujemy
            pass

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "filter_status": status,
        "only_final": only_final,
        # jeśli masz Status w MaintenanceProtocol – to zadziała; jak nie, możesz to usunąć
        "status_choices": getattr(MaintenanceProtocol, "Status", None).choices
        if hasattr(MaintenanceProtocol, "Status")
        else [],
    }
    return render(request, "core/maintenance_protocol_list.html", context)



@login_required
def workorder_detail(request, pk):
    order = get_object_or_404(
        WorkOrder.objects.select_related("site", "assigned_to", "job").prefetch_related("systems"),
        pk=pk,
    )

    protocol = getattr(order, "maintenance_protocol", None)

    # spróbujemy wyciągnąć powiązany protokół serwisowy (jeśli istnieje)
    service_report = getattr(order, "service_report", None)

    can_edit = is_office(request.user)

    context = {
        "order": order,
        "service_report": service_report,
        "can_edit": can_edit,
        "maintenance_protocol": protocol,
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

            # jeśli to zlecenie przeglądu okresowego – tworzymy protokół KS
            if order.work_type == WorkOrder.WorkOrderType.MAINTENANCE:
                # zabezpieczenie: nie twórz dwa razy
                if not hasattr(order, "maintenance_protocol"):
                    # Ustalamy okres przeglądu + datę wykonania na podstawie planned_date
                    if order.planned_date:
                        period_date = order.planned_date
                    else:
                        period_date = timezone.now().date()

                    period_year = period_date.year
                    period_month = period_date.month

                    next_year = None
                    next_month = None
                    if order.site:
                        next_year, next_month = order.site.get_next_maintenance_period(
                            from_year=period_year,
                            from_month=period_month,
                        )

                    protocol = MaintenanceProtocol.objects.create(
                        work_order=order,
                        site=order.site,
                        # ✅ NOWE: data wykonania przeglądu
                        date=period_date,
                        period_year=period_year,
                        period_month=period_month,
                        next_period_year=next_year,
                        next_period_month=next_month,
                    )

                    # Nadaj numer KS, jeśli jeszcze nie ma
                    protocol.assign_number_if_needed()

                    # Wygeneruj sekcje i punkty:
                    # - jeśli jest poprzedni protokół dla obiektu → kopiuj z niego
                    # - jeśli nie ma → domyślna checklista z systemów
                    protocol.initialize_sections_from_previous_or_default()

            return redirect("core:workorder_detail", pk=order.pk)
    else:
        # Inicjalizacja z parametrów GET (np. z modułu "Konserwacje na:")
        initial = {}

        # site=<id>
        site_id = request.GET.get("site")
        if site_id:
            try:
                initial["site"] = Site.objects.get(pk=site_id)
            except Site.DoesNotExist:
                pass

        # work_type=MAINTENANCE / SERVICE / JOB / OTHER
        work_type_param = request.GET.get("work_type")
        valid_work_types = {choice[0] for choice in WorkOrder.WorkOrderType.choices}
        if work_type_param in valid_work_types:
            initial["work_type"] = work_type_param

        # period=RRRR-MM – ustawiamy planned_date na 1. dzień tego miesiąca
        period_param = request.GET.get("period")
        if period_param:
            try:
                year_str, month_str = period_param.split("-")
                year = int(year_str)
                month = int(month_str)
                initial["planned_date"] = date(year, month, 1)
            except (ValueError, TypeError):
                pass

        form = WorkOrderForm(initial=initial)

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
            order = form.save()

            # ✅ NOWE: jeśli to MAINTENANCE i jest protokół KS – aktualizuj datę wykonania z terminu zlecenia
            if order.work_type == WorkOrder.WorkOrderType.MAINTENANCE and hasattr(order, "maintenance_protocol"):
                protocol = order.maintenance_protocol

                if order.planned_date:
                    period_date = order.planned_date
                else:
                    period_date = timezone.localdate()

                update_fields = []

                if protocol.date != period_date:
                    protocol.date = period_date
                    update_fields.append("date")

                if protocol.period_year != period_date.year:
                    protocol.period_year = period_date.year
                    update_fields.append("period_year")

                if protocol.period_month != period_date.month:
                    protocol.period_month = period_date.month
                    update_fields.append("period_month")

                # przelicz następny przegląd wg ustawień obiektu
                if order.site:
                    ny, nm = order.site.get_next_maintenance_period(
                        from_year=protocol.period_year,
                        from_month=protocol.period_month,
                    )
                    if protocol.next_period_year != ny:
                        protocol.next_period_year = ny
                        update_fields.append("next_period_year")
                    if protocol.next_period_month != nm:
                        protocol.next_period_month = nm
                        update_fields.append("next_period_month")

                if update_fields:
                    protocol.save(update_fields=update_fields)

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

        # flaga: czy system jest w umowie
        in_contract_flag = getattr(
            s,
            "in_service_contract",
            getattr(s, "in_contract", False),
        )

        data.append(
            {
                "id": s.id,
                "label": label,                     # UWAGA: bez "(w umowie)"
                "in_contract": bool(in_contract_flag),  # flaga do badga
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

@xframe_options_sameorigin
@login_required
def service_report_pdf(request, pk):
    report = get_object_or_404(ServiceReport, pk=pk)
    order = report.work_order

    items = report.items.all()
    items_total = items.aggregate(total=Sum("total_price"))["total"] or 0

    # baza nazwy pliku: numer protokołu albo fallback
    base_name = report.number or f"protokol_{report.pk}"

    # proste "oczyszczenie" – usuwamy spacje i ukośniki itp.
    safe_name = (
        base_name
        .replace("/", "_")
        .replace("\\", "_")
    )

    context = {
        "report": report,
        "order": order,
        "items": items,
        "items_total": items_total,
        "download_filename": safe_name,
    }
    return render(request, "core/servicereport_pdf.html", context)
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


@login_required
def maintenance_protocol_edit(request, pk):
    protocol = get_object_or_404(
        MaintenanceProtocol.objects.select_related("site", "work_order"),
        pk=pk,
    )

    site = protocol.site
    work_order = protocol.work_order

    # Wszystkie sekcje z punktami
    sections_qs = protocol.sections.all().prefetch_related("check_items")

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

                    # Zapisujemy uwagi (podsumowanie sekcji) dla każdej sekcji
                    for bundle in section_formsets:
                        section = bundle["section"]
                        remarks_field = f"section_{section.pk}_remarks"
                        new_remarks = (request.POST.get(remarks_field) or "").strip()

                        if new_remarks != (section.section_remarks or ""):
                            section.section_remarks = new_remarks
                            section.save(update_fields=["section_remarks"])

                        # zapisujemy też wyniki / notatki z checklisty
                        bundle["formset"].save()

                    return redirect("core:maintenance_protocol_detail", pk=protocol.pk)


    else:
        form = MaintenanceProtocolForm(instance=protocol)

        section_formsets = []
        for section in sections_qs:
            formset = MaintenanceCheckItemFormSet(
                queryset=section.check_items.all(),
                prefix=f"section-{section.pk}",
            )
            section_formsets.append({"section": section, "formset": formset})

    context = {
        "protocol": protocol,
        "site": site,
        "work_order": work_order,
        "form": form,
        "section_formsets": section_formsets,
    }
    return render(request, "core/maintenance_protocol_form.html", context)



@login_required
def maintenance_protocol_detail(request, pk):
    protocol = get_object_or_404(
        MaintenanceProtocol.objects.select_related("site", "work_order"),
        pk=pk,
    )

    context = {
        "protocol": protocol,
        "site": protocol.site,
        "work_order": protocol.work_order,
        "sections": protocol.sections.all().prefetch_related("check_items"),
        "can_edit": True,  # na razie prosto – każdy zalogowany; później możemy ograniczyć do biura
        # "can_edit": is_office(request.user),  # jeśli chcesz od razu tylko biuro
    }
    return render(request, "core/maintenance_protocol_detail.html", context)


@xframe_options_sameorigin
@login_required
def maintenance_protocol_pdf(request, pk):
    protocol = get_object_or_404(
        MaintenanceProtocol.objects.select_related("site", "work_order"),
        pk=pk,
    )

    sections = protocol.sections.all().prefetch_related("check_items")

    base_name = protocol.number or f"KS_{protocol.pk}"
    safe_name = base_name.replace("/", "_").replace("\\", "_")

    context = {
        "protocol": protocol,
        "site": protocol.site,
        "work_order": protocol.work_order,
        "sections": sections,
        "download_filename": safe_name,
    }
    return render(request, "core/maintenance_protocol_pdf.html", context)


@login_required
def maintenance_protocol_delete(request, pk):
    protocol = get_object_or_404(
        MaintenanceProtocol.objects.select_related("site", "work_order"),
        pk=pk,
    )

    if not is_office(request.user):
        return HttpResponseForbidden(
            "Brak uprawnień do usuwania protokołów konserwacji."
        )

    work_order_pk = protocol.work_order.pk if protocol.work_order_id else None

    if request.method == "POST":
        protocol.delete()

        # Po usunięciu: jeśli był powiązany ze zleceniem -> wróć do zlecenia,
        # w przeciwnym razie -> lista protokołów KS
        if work_order_pk:
            return redirect("core:workorder_detail", pk=work_order_pk)
        return redirect("core:maintenance_protocol_list")

    # GET -> wróć na szczegóły
    return redirect("core:maintenance_protocol_detail", pk=pk)

