from django.http import HttpResponseRedirect


class TechnicianPwaOnlyMiddleware:
    """
    Serwisanci (grupa 'technician') mają mieć dostęp tylko do PWA.
    Biuro (superuser lub grupa 'office') ma pełny dostęp do portalu.

    Jeśli serwisant wejdzie na URL inny niż dozwolony -> redirect na /pwa/
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # co serwisant może odpalać:
        self.allowed_prefixes = (
            "/pwa/",
            "/api/pwa/",
            "/accounts/",
            "/static/",
            "/media/",
        )

        # opcjonalne wyjątki (jakbyś kiedyś potrzebował)
        self.allowed_exact = {
            "/favicon.ico",
            "/robots.txt",
        }

    def __call__(self, request):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return self.get_response(request)

        # role
        is_office = user.is_superuser or user.groups.filter(name="office").exists()
        is_technician = user.groups.filter(name="technician").exists()

        # serwisant != biuro -> tylko PWA
        if is_technician and not is_office:
            path = request.path or "/"

            # pozwól na dozwolone ścieżki
            if path in self.allowed_exact or any(path.startswith(p) for p in self.allowed_prefixes):
                return self.get_response(request)

            # admin też blokujemy serwisantom (i tak nie powinni tam wchodzić)
            if path.startswith("/admin/"):
                return HttpResponseRedirect("/pwa/")

            # wszystko inne = portal -> przerzut na PWA
            return HttpResponseRedirect("/pwa/")

        return self.get_response(request)
