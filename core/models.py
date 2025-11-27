from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal



class Entity(models.Model):
    """Jednostka rozliczeniowa: wspólnota, firma, osoba prywatna itp."""

    class EntityType(models.TextChoices):
        WSPOLNOTA = "WSPOLNOTA", "Wspólnota mieszkaniowa"
        SPOLDZIELNIA = "SPOLDZIELNIA", "Spółdzielnia"
        FIRMA = "FIRMA", "Firma"
        OSOBA = "OSOBA", "Osoba prywatna"
        INNE = "INNE", "Inne"

    name = models.CharField("Nazwa", max_length=255)

    type = models.CharField(
        "Typ jednostki",
        max_length=20,
        choices=EntityType.choices,
        default=EntityType.FIRMA,
    )

    nip = models.CharField("NIP", max_length=20, blank=True)
    regon = models.CharField("REGON", max_length=20, blank=True)
    pesel = models.CharField("PESEL", max_length=11, blank=True)

    street = models.CharField("Ulica i nr", max_length=255, blank=True)
    postal_code = models.CharField("Kod pocztowy", max_length=10, blank=True)
    city = models.CharField("Miejscowość", max_length=100, blank=True)

    notes = models.TextField("Notatki", blank=True)

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Dane fakturowe"
        verbose_name_plural = "Dane fakturowe"

    def __str__(self):
        return self.name
    

class Manager(models.Model):
    """Zarządca nieruchomości / firma zarządzająca."""

    short_name = models.CharField(
        "Nazwa skrócona",
        max_length=255,
        help_text="Nazwa robocza, używana na co dzień.",
    )
    full_name = models.CharField(
        "Pełna nazwa",
        max_length=255,
        help_text="Pełna nazwa według danych rejestrowych.",
    )

    nip = models.CharField("NIP", max_length=20, blank=True)

    street = models.CharField("Ulica i nr", max_length=255, blank=True)
    postal_code = models.CharField("Kod pocztowy", max_length=10, blank=True)
    city = models.CharField("Miejscowość", max_length=100, blank=True)

    notes = models.TextField("Notatki", blank=True)

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Zarządca"
        verbose_name_plural = "Zarządcy"

    def __str__(self):
        return self.short_name or self.full_name


class Site(models.Model):
    """Obiekt / budynek / inwestycja, na którym wykonujemy serwis."""

    class SiteType(models.TextChoices):
        MIESZKALNY = "MIESZKALNY", "Mieszkalny"
        BIUROWY = "BIUROWY", "Biurowy"
        USLUGOWY = "USLUGOWY", "Usługowy"
        MAGAZYNOWY = "MAGAZYNOWY", "Magazynowy"
        INNY = "INNY", "Inny"

    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name="sites",
        verbose_name="Dane fakturowe",
    )

    manager = models.ForeignKey(
        "Manager",
        on_delete=models.SET_NULL,
        related_name="sites",
        verbose_name="Zarządca",
        blank=True,
        null=True,
        help_text="Firma zarządzająca tym obiektem (opcjonalnie).",
    )

    name = models.CharField("Nazwa obiektu", max_length=255)

    street = models.CharField("Ulica i nr", max_length=255, blank=True)
    postal_code = models.CharField("Kod pocztowy", max_length=10, blank=True)
    city = models.CharField("Miejscowość", max_length=100, blank=True)

    google_maps_url = models.URLField(
        "Link do Google Maps",
        max_length=500,
        blank=True,
        help_text="Wklej link do pinezki/obiektu z Google Maps, aby łatwo go otworzyć.",
    )

    site_type = models.CharField(
        "Typ obiektu",
        max_length=20,
        choices=SiteType.choices,
        default=SiteType.MIESZKALNY,
    )

    access_info = models.TextField(
        "Informacje o dostępie",
        blank=True,
        help_text="Np. gdzie są klucze, kody, portiernia, sposób wejścia.",
    )

    technical_notes = models.TextField(
        "Notatki techniczne",
        blank=True,
        help_text="Np. lokalizacja szaf, central, uwagi dla serwisanta.",
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Obiekt"
        verbose_name_plural = "Obiekty"

    def __str__(self):
        return f"{self.name} ({self.city})" if self.city else self.name



class Contact(models.Model):
    """Osoba kontaktowa: zarządca, administrator, właściciel, dozorca itp."""

    first_name = models.CharField("Imię", max_length=100, blank=True)
    last_name = models.CharField("Nazwisko", max_length=100, blank=True)
    phone = models.CharField("Telefon", max_length=50, blank=True)
    email = models.EmailField("E-mail", max_length=255, blank=True)

    manager = models.ForeignKey(
        Manager,
        on_delete=models.SET_NULL,
        related_name="contacts",
        verbose_name="Zarządca",
        blank=True,
        null=True,
        help_text="Jeśli osoba jest pracownikiem konkretnego zarządcy.",
    )

    notes = models.TextField("Notatki", blank=True)

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Osoba kontaktowa"
        verbose_name_plural = "Osoby kontaktowe"

    def __str__(self):
        fullname = f"{self.first_name} {self.last_name}".strip()
        return fullname or self.email or self.phone or "Kontakt"


class SiteContact(models.Model):
    """Powiązanie obiektu z kontaktem + rola (zarządca, administrator itd.)."""

    class Role(models.TextChoices):
        ZARZADCA = "ZARZADCA", "Zarządca"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrator"
        WLASCICIEL = "WLASCICIEL", "Właściciel"
        KONTAKT_AWARIE = "KONTAKT_AWARIE", "Kontakt ds. awarii"
        KONTAKT_ROZLICZENIA = "KONTAKT_ROZLICZENIA", "Kontakt ds. rozliczeń"
        INNY = "INNY", "Inna rola"

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="site_contacts",
        verbose_name="Obiekt",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="site_links",
        verbose_name="Kontakt",
    )
    role = models.CharField(
        "Rola",
        max_length=30,
        choices=Role.choices,
        default=Role.ZARZADCA,
    )
    is_default_for_notifications = models.BooleanField(
        "Domyślny do powiadomień",
        default=False,
        help_text="Domyślny adresat protokołów / informacji.",
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Powiązanie obiektu z kontaktem"
        verbose_name_plural = "Powiązania obiektów z kontaktami"
        unique_together = ("site", "contact", "role")

    def __str__(self):
        return f"{self.site} ↔ {self.contact} ({self.role})"


class System(models.Model):
    """System na obiekcie: CCTV, SSP, Alarm, Oddymianie, KD, Domofon, TV-SAT, Światłowód itp."""

    class SystemType(models.TextChoices):
        CCTV = "CCTV", "CCTV"
        SSP = "SSP", "System Sygnalizacji Pożaru"
        ALARM = "ALARM", "System alarmowy"
        ODDYM = "ODDYM", "Oddymianie"
        KD = "KD", "Kontrola dostępu"
        DOMOFON = "DOMOFON", "Domofon"
        VIDEODOMOFON = "VIDEODOMOFON", "Wideodomofon"
        TVSAT = "TVSAT", "TV naziemna / SAT"
        SWIATLOWOD = "SWIATLOWOD", "Światłowód"
        INNY = "INNY", "Inny system"

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="systems",
        verbose_name="Obiekt",
    )

    system_type = models.CharField(
        "Typ systemu",
        max_length=20,
        choices=SystemType.choices,
        default=SystemType.CCTV,
    )

    name = models.CharField(
        "Opis systemu (opcjonalnie)",
        max_length=255,
        blank=True,
        help_text="Np. 'CCTV garaż + wejścia', jeśli obiekt ma kilka systemów tego samego typu.",
    )

    manufacturer = models.CharField("Producent", max_length=100, blank=True)
    model = models.CharField("Model / centrala / rejestrator", max_length=100, blank=True)

    commissioning_date = models.DateField("Data uruchomienia", blank=True, null=True)
    last_modernization_date = models.DateField(
        "Data ostatniej modernizacji",
        blank=True,
        null=True,
    )

    in_service_contract = models.BooleanField(
        "W umowie serwisowej",
        default=False,
        help_text="Czy system jest objęty stałą umową serwisową.",
    )

    location_info = models.TextField(
        "Lokalizacja urządzeń",
        blank=True,
        help_text="Np. gdzie jest centrala, rejestrator, szafy, przyciski ROP itp.",
    )

    access_data = models.TextField(
        "Hasła / kody / dane dostępowe",
        blank=True,
        help_text="Dane wrażliwe – kody, loginy, hasła do urządzeń.",
    )

    procedures = models.TextField(
        "Procedury testowe / serwisowe",
        blank=True,
        help_text="Opis procedur testowych, uruchomieniowych, resetów itp.",
    )

    notes = models.TextField("Notatki techniczne", blank=True)

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "System na obiekcie"
        verbose_name_plural = "Systemy na obiektach"

    def __str__(self):
        base = self.get_system_type_display()
        if self.name:
            base = f"{self.name} ({base})"
        return f"{base} – {self.site}"

class Job(models.Model):
    """Robota / projekt: montaż, modernizacja, rozbudowa."""

    class JobType(models.TextChoices):
        NOWY_MONTAZ = "NOWY_MONTAZ", "Nowy montaż"
        MODERNIZACJA = "MODERNIZACJA", "Modernizacja"
        ROZBUDOWA = "ROZBUDOWA", "Rozbudowa"
        INNE = "INNE", "Inne"

    class JobStatus(models.TextChoices):
        PLANOWANA = "PLANOWANA", "Planowana"
        W_REALIZACJI = "W_REALIZACJI", "W realizacji"
        ZAWIESZONA = "ZAWIESZONA", "Zawieszona"
        ZAKONCZONA = "ZAKONCZONA", "Zakończona"
        ANULOWANA = "ANULOWANA", "Anulowana"

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name="Obiekt",
    )

    entity = models.ForeignKey(
        Entity,
        on_delete=models.SET_NULL,
        related_name="jobs",
        verbose_name="Dane fakturowe",
        blank=True,
        null=True,
        help_text="Jeśli inne niż domyślne dane fakturowe obiektu.",
    )

    manager = models.ForeignKey(
        Manager,
        on_delete=models.SET_NULL,
        related_name="jobs",
        verbose_name="Zarządca",
        blank=True,
        null=True,
        help_text="Jeśli inny niż domyślny zarządca obiektu.",
    )

    main_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        related_name="jobs_as_main_contact",
        verbose_name="Główna osoba kontaktowa",
        blank=True,
        null=True,
    )

    job_type = models.CharField(
        "Typ robót",
        max_length=20,
        choices=JobType.choices,
        default=JobType.NOWY_MONTAZ,
    )

    title = models.CharField(
        "Nazwa robót",
        max_length=255,
        help_text="Krótka nazwa, np. 'Montaż CCTV garaż P25–33'.",
    )

    description = models.TextField(
        "Opis / zakres robót",
        blank=True,
        help_text="Szczegółowy zakres prac zgodnie z ofertą/umową.",
    )

    status = models.CharField(
        "Status robót",
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PLANOWANA,
    )

    planned_start_date = models.DateField(
        "Planowany start",
        blank=True,
        null=True,
    )
    planned_end_date = models.DateField(
        "Planowane zakończenie",
        blank=True,
        null=True,
    )

    actual_start_date = models.DateField(
        "Rzeczywisty start",
        blank=True,
        null=True,
    )
    actual_end_date = models.DateField(
        "Rzeczywiste zakończenie",
        blank=True,
        null=True,
    )

    offer_number = models.CharField(
        "Numer oferty",
        max_length=100,
        blank=True,
    )
    contract_number = models.CharField(
        "Numer umowy / zlecenia",
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        "Notatki wewnętrzne",
        blank=True,
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Robota"
        verbose_name_plural = "Roboty"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} – {self.site}"

class WorkOrder(models.Model):
    """Zlecenie: przegląd, serwis lub wyjazd w ramach robót."""

    class WorkOrderType(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Przegląd okresowy"
        SERVICE = "SERVICE", "Serwis awaryjny"
        JOB = "JOB", "Robota / montaż (wyjazd)"
        OTHER = "OTHER", "Inne"

    class Status(models.TextChoices):
        NEW = "NEW", "Nowe"
        SCHEDULED = "SCHEDULED", "Umówione"
        IN_PROGRESS = "IN_PROGRESS", "W realizacji"
        WAITING_FOR_DECISION = "WAITING_FOR_DECISION", "Czeka na decyzję klienta"
        WAITING_FOR_PARTS = "WAITING_FOR_PARTS", "Czeka na materiał"
        COMPLETED = "COMPLETED", "Zakończone"
        CANCELLED = "CANCELLED", "Odwołane"

    class Priority(models.TextChoices):
        NORMAL = "NORMAL", "Normalny"
        HIGH = "HIGH", "Wysoki"
        CRITICAL = "CRITICAL", "Krytyczny"

    class VisitType(models.TextChoices):
        FLEXIBLE = "FLEXIBLE", "W ciągu dnia"
        WINDOW = "WINDOW", "Na przedział godzinowy"


    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="work_orders",
        verbose_name="Obiekt",
    )

    systems = models.ManyToManyField(
        System,
        blank=True,
        related_name="work_orders",
        verbose_name="Systemy objęte zleceniem",
        help_text="Jeśli zlecenie dotyczy konkretnych systemów na obiekcie, wybierz je tutaj.",
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        related_name="work_orders",
        verbose_name="Robota",
        blank=True,
        null=True,
        help_text="Jeśli zlecenie jest częścią konkretnej roboty (montaż/modernizacja).",
    )


    work_type = models.CharField(
        "Typ zlecenia",
        max_length=20,
        choices=WorkOrderType.choices,
        default=WorkOrderType.SERVICE,
    )

    title = models.CharField(
        "Tytuł / krótki opis",
        max_length=255,
        help_text="Np. 'Awaria domofonu kl. B', 'Przegląd SSP Q1/2025'.",
    )

    description = models.TextField(
        "Opis zgłoszenia / zakres prac",
        blank=True,
    )

    internal_notes = models.TextField(
        "Notatki wewnętrzne",
        blank=True,
    )

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name="Status",
    )


    priority = models.CharField(
        "Priorytet",
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    requested_by = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        related_name="requested_work_orders",
        verbose_name="Zgłaszający (kontakt)",
        blank=True,
        null=True,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_work_orders",
        verbose_name="Przypisano do",
        blank=True,
        null=True,
    )

    planned_date = models.DateField(
        "Planowana data wizyty",
        blank=True,
        null=True,
    )

    visit_type = models.CharField(
        max_length=16,
        choices=VisitType.choices,
        default=VisitType.FLEXIBLE,
        verbose_name="Rodzaj wizyty",
    )

    planned_time_from = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Godzina od",
    )

    planned_time_to = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Godzina do",
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)
    closed_at = models.DateTimeField("Data zamknięcia", blank=True, null=True)

    class Meta:
        verbose_name = "Zlecenie"
        verbose_name_plural = "Zlecenia"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} {self.title}"
    

class ServiceReport(models.Model):
    """Protokół serwisowy do zlecenia typu SERWIS."""

    class ServiceMode(models.TextChoices):
        WARRANTY = "WARRANTY", "Gwarancja"
        CONTRACT = "CONTRACT", "Umowa"
        PAID = "PAID", "Płatny"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Gotówka"
        TRANSFER = "TRANSFER", "Przelew"
        CONTRACT = "CONTRACT", "Zgodnie z umową"

    class Result(models.TextChoices):
        REPAIRED = "REPAIRED", "Usterka usunięta"
        TEMPORARY = "TEMPORARY", "Przywrócono pracę czasowo"
        NOT_FIXED = "NOT_FIXED", "Nie usunięto usterki"
        INSPECTION_ONLY = "INSPECTION_ONLY", "Sprawdzenie / diagnostyka"

    work_order = models.OneToOneField(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="service_report",
        verbose_name="Zlecenie",
        help_text="Zlecenie, którego dotyczy ten protokół (typu Serwis awaryjny).",
    )

    number = models.CharField(
        "Numer protokołu",
        max_length=20,
        blank=True,
        help_text="Jeśli puste, numer zostanie nadany automatycznie w formacie 'PS 01-11-2025'.",
    )

    report_date = models.DateField("Data protokołu", blank=True, null=True)

    service_mode = models.CharField(
        "Tryb serwisu",
        max_length=20,
        choices=ServiceMode.choices,
        blank=True,
        help_text="Gwarancja / Umowa / Płatny.",
    )

    payment_method = models.CharField(
        "Forma płatności",
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
    )

    # 1) zgłaszający + telefon, obok siebie + kontakt do zarządcy/zgłaszającego
    requester_name = models.CharField(
        "Osoba zgłaszająca",
        max_length=255,
        blank=True,
        help_text="Kontakt do osoby zgłaszającej / zarządzającej obiektem.",
    )
    requester_phone = models.CharField(
        "Telefon zgłaszającego",
        max_length=50,
        blank=True,
        help_text="Telefon do osoby zgłaszającej / zarządzającej obiektem.",
    )

    description_before = models.TextField(
        "Opis usterki / stan przed",
        blank=True,
        help_text="Jaką usterkę zgłoszono, jaki był stan systemu przed podjęciem prac.",
    )

    work_performed = models.TextField(
        "Opis wykonanych prac",
        blank=True,
    )

    result = models.CharField(
        "Wynik",
        max_length=20,
        choices=Result.choices,
        blank=True,
    )

    next_actions = models.TextField(
        "Zalecenia / dalsze kroki",
        blank=True,
        help_text="Np. konieczność wymiany elementów, ponowna wizyta, oferta.",
    )

    # 4) serwisanci – docelowo auto z przydzielonego zlecenia
    technicians = models.CharField(
        "Serwisanci",
        max_length=255,
        blank=True,
        help_text="Automatycznie uzupełniane na podstawie zlecenia (przypisanego pracownika).",
    )

    # 2) USUWAMY: material_security
    # 3) USUWAMY: invoice_data

    notes_internal = models.TextField(
        "Notatki wewnętrzne",
        blank=True,
        help_text="Widoczne tylko wewnętrznie, nie drukują się na protokole dla klienta.",
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Protokół serwisowy"
        verbose_name_plural = "Protokoły serwisowe"

    def __str__(self):
        if self.number:
            return f"{self.number} (zlecenie #{self.work_order_id})"
        return f"Protokół serwisowy dla zlecenia #{self.work_order_id}"

    def clean(self):
        """Pilnujemy, że protokół serwisowy jest podpięty pod zlecenie typu SERWIS."""
        from django.core.exceptions import ValidationError

        if self.work_order and self.work_order.work_type != WorkOrder.WorkOrderType.SERVICE:
            raise ValidationError(
                {"work_order": "Protokół serwisowy można podpiąć tylko do zlecenia typu 'Serwis awaryjny'."}
            )

    def save(self, *args, **kwargs):
        """
        Automatyczna numeracja:
        PS XX-MM-RRRR, np. 'PS 01-11-2025':
        - XX: kolejny numer protokołu w danym miesiącu/roku,
        - MM: miesiąc,
        - RRRR: rok.

        Dodatkowo:
        - jeśli brak osoby zgłaszającej/telefonu -> uzupełnij z work_order.requested_by,
        - jeśli brak serwisantów -> uzupełnij z work_order.assigned_to.
        """
        # domyślna data protokołu = dziś, jeśli nie ustawiono
        if not self.report_date:
            self.report_date = timezone.localdate()

        # auto numeracja, jeśli brak numeru
        if not self.number:
            year = self.report_date.year
            month = self.report_date.month

            count = (
                ServiceReport.objects.filter(
                    report_date__year=year,
                    report_date__month=month,
                )
                .exclude(pk=self.pk)
                .count()
            )
            next_number = count + 1
            self.number = f"PS {next_number:02d}-{month:02d}-{year}"

        # auto zgłaszający + telefon z work_order.requested_by
        if self.work_order and self.work_order.requested_by:
            contact = self.work_order.requested_by
            full_name = f"{contact.first_name} {contact.last_name}".strip()
            if not self.requester_name and full_name:
                self.requester_name = full_name
            if not self.requester_phone and contact.phone:
                self.requester_phone = contact.phone

        # auto opis usterki ze zlecenia, jeśli pusty
        if (
            self.work_order
            and not self.description_before
            and self.work_order.description
        ):
            self.description_before = self.work_order.description

        # auto serwisant z work_order.assigned_to
        if self.work_order and self.work_order.assigned_to and not self.technicians:
            user = self.work_order.assigned_to
            full_name = getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "")
            if full_name:
                self.technicians = full_name

        super().save(*args, **kwargs)



class ServiceReportItem(models.Model):
    """Pozycja rozliczeniowa na protokole serwisowym (RBH, dojazd, materiały…)."""

    class Unit(models.TextChoices):
        RBH = "RBH", "rbh"
        PIECE = "SZT", "szt."
        KM = "KM", "km"
        OTHER = "INNE", "inne"

    report = models.ForeignKey(
        ServiceReport,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Protokół serwisowy",
    )

    description = models.CharField("Opis pozycji", max_length=255)
    quantity = models.DecimalField("Ilość", max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(
        "Jm",
        max_length=10,
        choices=Unit.choices,
        default=Unit.RBH,
    )
    unit_price = models.DecimalField(
        "Cena jedn. netto",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    total_price = models.DecimalField(
        "Wartość netto",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Może być liczone automatycznie jako ilość × cena jedn.",
    )

    order_index = models.PositiveIntegerField(
        "Kolejność",
        default=0,
        help_text="Do sortowania pozycji na protokole.",
    )

    class Meta:
        verbose_name = "Pozycja protokołu serwisowego"
        verbose_name_plural = "Pozycje protokołu serwisowego"
        ordering = ["order_index", "id"]

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        # 5) automatyczne liczenie wartości netto = ilość × cena jedn.
        if self.unit_price is not None and self.quantity is not None:
            self.total_price = (self.unit_price or Decimal("0")) * self.quantity
        super().save(*args, **kwargs)


