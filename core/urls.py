from django.urls import path
from . import views
from . import views_pwa


app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("pwa/", views_pwa.pwa_home, name="pwa_home"),
    path("api/pwa/catalog/dump/", views_pwa.api_pwa_catalog_dump, name="api_pwa_catalog_dump"),
    path("pwa/obiekty/", views_pwa.pwa_objects, name="pwa_objects"),
    path("pwa/zlecenia/", views_pwa.pwa_workorder_list, name="pwa_workorder_list"),
    path("pwa/zlecenia/<int:pk>/", views_pwa.pwa_workorder_detail, name="pwa_workorder_detail"),

    path("pwa/sw.js", views_pwa.pwa_sw, name="pwa_sw"),
    path("api/pwa/ping/", views_pwa.api_pwa_ping, name="api_pwa_ping"),

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

        # DANE FAKTUROWE (Entity)
    path("dane-fv/", views.entity_list, name="entity_list"),
    path("dane-fv/nowe/", views.entity_create, name="entity_create"),
    path("dane-fv/<int:pk>/", views.entity_detail, name="entity_detail"),
    path("dane-fv/<int:pk>/edytuj/", views.entity_edit, name="entity_edit"),
    path("dane-fv/<int:pk>/usun/", views.entity_delete, name="entity_delete"),


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

    # AJAX – kontakty dla obiektu
    path(
        "ajax/sites/<int:site_id>/contacts/",
        views.site_contacts_json,
        name="site_contacts_json",
    ),

    path(
        "protokoly-przegladow/<int:pk>/",
        views.maintenance_protocol_detail,
        name="maintenance_protocol_detail",
    ),

    path(
        "protokoly-przegladow/<int:pk>/edytuj/",
        views.maintenance_protocol_edit,
        name="maintenance_protocol_edit",
    ),
    path(
        "protokoly-przegladow/<int:pk>/pdf/",
        views.maintenance_protocol_pdf,
        name="maintenance_protocol_pdf",
    ),
    path(
        "protokoly-przegladow//<int:pk>/usun/",
        views.maintenance_protocol_delete,
        name="maintenance_protocol_delete",
    ),

    path(
        "protokoly-przegladow/",
        views.maintenance_protocol_list,
        name="maintenance_protocol_list",
    ),
]


