from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("zlecenia/", views.workorder_list, name="workorder_list"),
    path("zlecenia/nowe/", views.workorder_create, name="workorder_create"),
    path("zlecenia/<int:pk>/", views.workorder_detail, name="workorder_detail"),

    path(
        "ajax/site/<int:site_id>/systems/",
        views.ajax_site_systems,
        name="ajax_site_systems",
    ),
]

