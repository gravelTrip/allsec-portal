from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import WorkOrder


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
