from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("zlecenia/", views.workorder_list, name="workorder_list"),
    path("zlecenia/nowe/", views.workorder_create, name="workorder_create"),
    path("zlecenia/<int:pk>/", views.workorder_detail, name="workorder_detail"),
    path("zlecenia/<int:pk>/edytuj/", views.workorder_edit, name="workorder_edit"),
    path(
        "zlecenia/<int:pk>/protokol/",
        views.service_report_entry,
        name="service_report_entry",
    ),
    path(
        "protokoly/",
        views.service_report_list,
        name="service_report_list",
    ),
    path(
        "protokoly/<int:pk>/",
        views.service_report_detail,
        name="service_report_detail",
    ),
    path(
        "protokoly/<int:pk>/edycja/",
        views.service_report_edit,
        name="service_report_edit",
    ),

    # Obiekty
    path("obiekty/", views.site_list, name="site_list"),
    path("obiekty/nowy/", views.site_create, name="site_create"),
    path("obiekty/<int:pk>/", views.site_detail, name="site_detail"),
    path("obiekty/<int:pk>/edytuj/", views.site_edit, name="site_edit"),
    path("obiekty/<int:pk>/usun/", views.site_delete, name="site_delete"),

    # Kontakty
    path("kontakty/", views.contact_list, name="contact_list"),
    path("kontakty/nowy/", views.contact_create, name="contact_create"),
    path("kontakty/<int:pk>/", views.contact_detail, name="contact_detail"),
    path("kontakty/<int:pk>/edytuj/", views.contact_edit, name="contact_edit"),
    path("kontakty/<int:pk>/usun/", views.contact_delete, name="contact_delete"),

    # Zarządcy
    path("zarzadcy/", views.manager_list, name="manager_list"),
    path("zarzadcy/nowy/", views.manager_create, name="manager_create"),
    path("zarzadcy/<int:pk>/", views.manager_detail, name="manager_detail"),
    path("zarzadcy/<int:pk>/edytuj/", views.manager_edit, name="manager_edit"),
    path("zarzadcy/<int:pk>/usun/", views.manager_delete, name="manager_delete"),

    path(
        "ajax/site/<int:site_id>/systems/",
        views.ajax_site_systems,
        name="ajax_site_systems",
    ),
    path(
        "protokoly/<int:pk>/pdf/",
        views.service_report_pdf,
        name="service_report_pdf",
    ),
     # Systemy na obiekcie
    path(
        "obiekty/<int:site_pk>/systemy/nowy/",
        views.system_create_for_site,
        name="system_create_for_site",
    ),
    path(
        "systemy/<int:pk>/",
        views.system_detail,
        name="system_detail",
    ),
    path(
        "systemy/<int:pk>/edytuj/",
        views.system_edit,
        name="system_edit",
    ),
    path(
        "systemy/<int:pk>/usun/",
        views.system_delete,
        name="system_delete",
    ),

    # Powiązane kontakty (SiteContact)
    path(
        "obiekty/<int:site_pk>/powiazane-kontakty/nowy/",
        views.sitecontact_create,
        name="sitecontact_create",
    ),
    path(
        "powiazane-kontakty/<int:pk>/",
        views.sitecontact_detail,
        name="sitecontact_detail",
    ),
    path(
        "powiazane-kontakty/<int:pk>/edytuj/",
        views.sitecontact_edit,
        name="sitecontact_edit",
    ),
    path(
        "powiazane-kontakty/<int:pk>/usun/",
        views.sitecontact_delete,
        name="sitecontact_delete",
    ),
]


