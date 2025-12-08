from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.db.models import Max

from datetime import date
from django.utils.translation import gettext_lazy as _
import calendar


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

    class MaintenanceFrequency(models.TextChoices):
        NONE = "NONE", _("Brak stałych przeglądów")
        MONTHLY = "MONTHLY", _("Co miesiąc")
        QUARTERLY = "QUARTERLY", _("Co kwartał")
        SEMIANNUAL = "SEMIANNUAL", _("2x w roku")
        CUSTOM = "CUSTOM", _("Wg wybranych miesięcy")

    maintenance_frequency = models.CharField(
        max_length=15,
        choices=MaintenanceFrequency.choices,
        default=MaintenanceFrequency.NONE,
        verbose_name="Częstotliwość przeglądów",
        help_text="Określa schemat przeglądów okresowych na obiekcie.",
    )

    maintenance_start_month = models.PositiveSmallIntegerField(
        choices=[(i, f"{i:02d}") for i in range(1, 13)],
        null=True,
        blank=True,
        verbose_name="Miesiąc startowy przeglądów",
        help_text="Używane dla schematów co miesiąc / kwartał / 2x w roku.",
    )

    maintenance_execution_month_in_period = models.PositiveSmallIntegerField(
        default=1,
        null=True,
        blank=True,
        verbose_name="Miesiąc wykonania w okresie",
        help_text=(
            "Dla przeglądów co kwartał: 1–3 (1 = pierwszy miesiąc kwartału itd.). "
            "Dla 2x w roku: 1–6. Dla miesięcznych zazwyczaj 1."
        ),
    )

    # Prosty sposób na custom: lista miesięcy 1–12 jako tekst, np. '1,4,7,10'
    maintenance_custom_months = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Miesiące przeglądów (CUSTOM)",
        help_text="Lista miesięcy 1–12 rozdzielona przecinkami, np. '1,4,7,10'.",
    )

    @property
    def maintenance_months(self):
        """
        Zwraca posortowaną listę miesięcy (1–12),
        w których przypadają przeglądy dla tego obiektu.
        """
        freq = self.maintenance_frequency
        if freq == self.MaintenanceFrequency.NONE:
            return []

        # CUSTOM – parsujemy maintenance_custom_months
        if freq == self.MaintenanceFrequency.CUSTOM:
            if not self.maintenance_custom_months:
                return []
            try:
                nums = [
                    int(x)
                    for x in self.maintenance_custom_months.split(",")
                    if x.strip()
                ]
                # filtrujemy miesiące poza zakresem
                months = sorted({m for m in nums if 1 <= m <= 12})
                return months
            except ValueError:
                return []

        # Pozostałe schematy wymagają miesiąca startowego
        start = self.maintenance_start_month
        if not start:
            return []

        if freq == self.MaintenanceFrequency.MONTHLY:
            return list(range(1, 13))

        if freq == self.MaintenanceFrequency.QUARTERLY:
            return sorted(((start + i * 3 - 1) % 12) + 1 for i in range(4))

        if freq == self.MaintenanceFrequency.SEMIANNUAL:
            return sorted(((start + i * 6 - 1) % 12) + 1 for i in range(2))

        return []
    
    @property
    def execution_months(self):
        """
        Zwraca listę nazw miesięcy, w których faktycznie wykonujemy konserwacje
        (wg maintenance_execution_month_in_period).
        """
        freq = self.maintenance_frequency
        start = self.maintenance_start_month
        exec_in_period = self.maintenance_execution_month_in_period or 1

        if not freq or not start:
            return []

        months = []

        if freq == self.MaintenanceFrequency.MONTHLY:
            # co miesiąc – wszystkie miesiące
            months = list(range(1, 13))
        elif freq == self.MaintenanceFrequency.QUARTERLY:
            period_length = 3
            for i in range(4):
                period_start = (start - 1 + i * period_length) % 12  # 0..11
                exec_idx = period_start + (exec_in_period - 1)
                months.append(exec_idx % 12 + 1)
        elif freq == self.MaintenanceFrequency.SEMIANNUAL:
            period_length = 6
            for i in range(2):
                period_start = (start - 1 + i * period_length) % 12
                exec_idx = period_start + (exec_in_period - 1)
                months.append(exec_idx % 12 + 1)
        else:
            # CUSTOM lub None – na razie nie wyliczamy, żeby nie zgadywać
            return []

        # Zamień na polskie nazwy miesięcy
        month_names = []
        for m in sorted(set(months)):
            # calendar.month_name[1] = "January" – u Ciebie i tak jest UI PL,
            # więc możesz to później podmienić na własną mapę nazw.
            month_names.append(str(m).zfill(2))
        return month_names



    def get_next_maintenance_period(self, from_year: int, from_month: int):
        """
        Zwraca (year, month) dla następnego planowego przeglądu
        liczonego względem PODANEGO miesiąca wykonania (rok, miesiąc).

        - MIESIĘCZNIE: +1 miesiąc
        - KWARTALNIE: +3 miesiące
        - 2x W ROKU:  +6 miesięcy
        - CUSTOM:     wg maintenance_custom_months (jak dotychczas)
        """
        freq = self.maintenance_frequency

        # zabezpieczenie na bzdurne dane
        if not (1 <= from_month <= 12):
            return None, None

        # CUSTOM – zostawiamy starą logikę opartą o maintenance_months
        if freq == self.MaintenanceFrequency.CUSTOM:
            months = self.maintenance_months
            if not months:
                return None, None

            current_year = from_year
            current_month = from_month

            future_months = [m for m in months if m > current_month]
            if future_months:
                return current_year, min(future_months)

            return current_year + 1, min(months)

        # Brak stałych przeglądów
        if freq == self.MaintenanceFrequency.NONE:
            return None, None

        # MIESIĘCZNIE – po prostu kolejny miesiąc
        if freq == self.MaintenanceFrequency.MONTHLY:
            if from_month == 12:
                return from_year + 1, 1
            return from_year, from_month + 1

        # Helper do przesuwania o N miesięcy z obsługą przełomu roku
        def add_months(year: int, month: int, delta: int):
            total = year * 12 + (month - 1) + delta
            new_year = total // 12
            new_month = (total % 12) + 1
            return new_year, new_month

        # KWARTALNIE – +3 miesiące od wykonania
        if freq == self.MaintenanceFrequency.QUARTERLY:
            return add_months(from_year, from_month, 3)

        # 2x W ROKU – +6 miesięcy od wykonania
        if freq == self.MaintenanceFrequency.SEMIANNUAL:
            return add_months(from_year, from_month, 6)

        # fallback
        return None, None

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
        CCTV = "CCTV", "System CCTV"
        SSP = "SSP", "System SSP"
        ALARM = "ALARM", "System SSWiN"
        ODDYM = "ODDYM", "System Oddymiania"
        KD = "KD", "System Kontroli Dostępu"
        DOMOFON = "DOMOFON", "Domofon"  # zostaje tylko dla starych wpisów
        VIDEODOMOFON = "VIDEODOMOFON", "System Video/Domofonowy"
        TVSAT = "TVSAT", "System RTV/SAT"
        SWIATLOWOD = "SWIATLOWOD", "Sieci LAN/OPTO"
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
    
    def get_maintenance_category(self) -> str | None:
        """
        Zwraca nazwę kategorii konserwacyjnej:
        'SSP', 'ODDYM', 'CCTV', 'VIDEODOMOFON', 'KD', 'SSWIN', 'RTV_SAT'
        albo None, jeśli system nie ma dedykowanej sekcji w protokole KS.
        """
        st = self.SystemType
        t = self.system_type

        if t == st.SSP:
            return "SSP"
        if t == st.ODDYM:
            return "ODDYM"
        if t == st.CCTV:
            return "CCTV"
        if t in (st.VIDEODOMOFON, st.DOMOFON):
            # klasyczny domofon też wrzucimy do sekcji Video/Domofon
            return "VIDEODOMOFON"
        if t == st.KD:
            return "KD"
        if t == st.ALARM:
            return "SSWIN"
        if t == st.TVSAT:
            return "RTV_SAT"

        # Sieci LAN/OPTO i Inne systemy na razie nie mają osobnych sekcji KS
        # (można będzie dodać później, jeśli będzie potrzeba)
        return None

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
        MAINTENANCE = "MAINTENANCE", "Konserwacja"
        SERVICE = "SERVICE", "Serwis"
        JOB = "JOB", "Montaż"
        OTHER = "OTHER", "Inne"

    class Status(models.TextChoices):
        NEW = "NEW", "Nowe"
        SCHEDULED = "SCHEDULED", "Umówione"
        IN_PROGRESS = "IN_PROGRESS", "W realizacji"
        WAITING_FOR_DECISION = "WAITING_FOR_DECISION", "Czeka na decyzję klienta"
        WAITING_FOR_PARTS = "WAITING_FOR_PARTS", "Czeka na materiał"
        COMPLETED = "COMPLETED", "Zakończone"
        CANCELLED = "CANCELLED", "Odwołane"

    class VisitType(models.TextChoices):
        FLEXIBLE = "FLEXIBLE", "W ciągu dnia"
        WINDOW = "WINDOW", "Na przedział godzinowy"


    number = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Numer zlecenia",
    )

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
        help_text="Np. 'Awaria domofonu kl. B', 'Konserwacja SSP Q1/2025'.",
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
        blank=True,
        null=True,
        verbose_name="Termin realizacji"
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
    
    def _set_maintenance_title_and_description(self):
        """
        Ustawia domyślny tytuł i opis dla zleceń typu MAINTENANCE,
        jeśli nie zostały podane ręcznie.
        """
        from .models import WorkOrder  # lokalny import, żeby uniknąć pętli

        if self.work_type != WorkOrder.WorkOrderType.MAINTENANCE:
            return

        # Okres bierzemy z planned_date, a jeśli brak – z dzisiejszej daty
        period_date = self.planned_date or date.today()
        period_str = period_date.strftime("%m-%Y")

        if not self.title:
            self.title = f"Konserwacja {period_str}"

        if not self.description:
            self.description = (
                f"Wykonanie konserwacji okresowej na obiekcie za {period_str}"
            )
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            self._set_maintenance_title_and_description()
        # jeśli numer nie ustawiony – wygeneruj
        if not self.number:
            today = timezone.localdate()
            month_str = f"{today.month:02d}"
            year_str = str(today.year)

            # sufiks daty: MM-YYYY, np. "11-2025"
            date_suffix = f"{month_str}-{year_str}"

            # policz ile zleceń już ma numer z tym sufiksem
            # np. "ZL 01-11-2025", "ZL 02-11-2025" itd.
            base_qs = WorkOrder.objects.filter(number__endswith=date_suffix)
            count = base_qs.count() + 1

            self.number = f"ZL {count:02d}-{date_suffix}"

        super().save(*args, **kwargs)

class MaintenanceProtocol(models.Model):
    """Protokół konserwacji (przegląd okresowy) powiązany ze zleceniem MAINTENANCE."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "W edycji"
        CLOSED = "CLOSED", "Zamknięty"

    work_order = models.OneToOneField(
        "WorkOrder",
        on_delete=models.CASCADE,
        related_name="maintenance_protocol",
        verbose_name="Zlecenie przeglądu",
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="maintenance_protocols",
        verbose_name="Obiekt",
    )

    number = models.CharField(
        "Numer protokołu",
        max_length=50,
        null=True,
        blank=True,
        help_text="Numer w formacie KS {kolejny}/{MM}/{RRRR}.",
    )

    sequence_number = models.PositiveIntegerField(
        "Kolejny numer w roku",
        blank=True,
        null=True,
        help_text="Numer porządkowy KS w danym roku.",
    )

    period_month = models.PositiveSmallIntegerField(
        "Miesiąc okresu przeglądu",
        blank=True,
        null=True,
    )

    period_year = models.PositiveSmallIntegerField(
        "Rok okresu przeglądu",
        blank=True,
        null=True,
    )

    date = models.DateField(
        "Data wykonania przeglądu",
        blank=True,
        null=True,
    )

    next_period_month = models.PositiveSmallIntegerField(
        "Miesiąc następnego przeglądu",
        blank=True,
        null=True,
    )

    next_period_year = models.PositiveSmallIntegerField(
        "Rok następnego przeglądu",
        blank=True,
        null=True,
    )

    status = models.CharField(
        "Status",
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Protokół konserwacji"
        verbose_name_plural = "Protokoły konserwacji"
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"KS (ID {self.pk})"
    
    def build_default_sections_from_site(self) -> int:
        """
        Tworzy sekcje i domyślne punkty kontroli na podstawie systemów na obiekcie
        (lub systemów zaznaczonych w zleceniu jako „objęte zleceniem”).
        Zwraca liczbę utworzonych sekcji.
        """

        # Upewniamy się, że mamy przypisany obiekt
        if not self.site and self.work_order and self.work_order.site:
            self.site = self.work_order.site
            self.save(update_fields=["site"])

        if not self.site:
            return 0

        # Jeśli sekcje już istnieją – nie dublujemy
        if self.sections.exists():
            return self.sections.count()

        from .models import (
            MAINTENANCE_SECTION_HEADERS,
            MAINTENANCE_DEFAULT_CHECKS,
            System,
        )

        # 1) Priorytet: systemy zaznaczone w zleceniu
        systems_qs = None
        if self.work_order_id:
            selected = self.work_order.systems.all()
            if selected.exists():
                systems_qs = selected

        # 2) Jeśli w zleceniu NIC nie zaznaczono → bierzemy wszystkie „w umowie”
        if systems_qs is None:
            systems_qs = System.objects.filter(
                site=self.site,
                in_service_contract=True,
            )

        systems = systems_qs.select_related("site").order_by(
            "system_type", "manufacturer", "model"
        )

        order_counter = 0
        created_sections = 0

        for system in systems:
            category = system.get_maintenance_category()
            if not category:
                # Np. Sieci LAN/OPTO albo Inny – na razie je pomijamy w KS
                continue

            header = MAINTENANCE_SECTION_HEADERS.get(category)
            checks = MAINTENANCE_DEFAULT_CHECKS.get(category, [])
            if not header or not checks:
                continue

            section = MaintenanceSection.objects.create(
                protocol=self,
                system=system,
                system_type=category,
                header_name=header,
                manufacturer=system.manufacturer or "",
                model=system.model or "",
                location=system.location_info or "",
                order=order_counter,
            )

            for idx, label in enumerate(checks, start=1):
                MaintenanceCheckItem.objects.create(
                    section=section,
                    order=idx,
                    label=label,
                )

            created_sections += 1
            order_counter += 1

        return created_sections

    def assign_number_if_needed(self, force: bool = False) -> None:
        """
        Nadaje numer protokołu i kolejny numer w MIESIĄCU.
        Format (wg Twojej zmiany): KS {kolejny}-{MM}-{RRRR}
        """
        # Jeśli numer już jest i nie wymuszamy nadania – nic nie rób
        if self.number and not force:
            return

        # Bez okresu nie nadamy sensownego numeru
        if not self.period_year or not self.period_month:
            return

        # Szukamy maksymalnego sequence_number dla danego ROKU i MIESIĄCA
        qs = MaintenanceProtocol.objects.filter(
            period_year=self.period_year,
            period_month=self.period_month,
        ).exclude(pk=self.pk)

        agg = qs.aggregate(max_seq=Max("sequence_number"))
        last_seq = agg["max_seq"] or 0

        next_seq = last_seq + 1

        self.sequence_number = next_seq
        # TU możesz zostawić dokładnie swój format;
        # przykładowo:
        self.number = f"KS {next_seq}-{self.period_month:02d}-{self.period_year}"

        self.save(update_fields=["sequence_number", "number"])

    
    def initialize_sections_from_previous_or_default(self) -> int:
        """
        Dla KAŻDEGO systemu objętego tym protokołem:
        - próbujemy skopiować ostatnią sekcję KS dla tego systemu na tym obiekcie
          (łącznie z wynikami i uwagami),
        - jeśli nie znajdziemy żadnej wcześniejszej sekcji – tworzymy sekcję
          z domyślnej checklisty dla danej kategorii.
        Zwraca liczbę utworzonych sekcji.
        """

        # Jeśli sekcje już istnieją – nic nie rób
        if self.sections.exists():
            return self.sections.count()

        # Upewniamy się, że mamy przypisany obiekt
        if not self.site and self.work_order and self.work_order.site:
            self.site = self.work_order.site
            self.save(update_fields=["site"])

        if not self.site:
            return 0

        # 1) Ustalamy listę systemów:
        #    - najpierw te zaznaczone w zleceniu,
        #    - jeśli brak -> wszystkie "w umowie" na obiekcie.
        systems_qs = None
        if self.work_order_id:
            selected = self.work_order.systems.all()
            if selected.exists():
                systems_qs = selected

        if systems_qs is None:
            systems_qs = System.objects.filter(
                site=self.site,
                in_service_contract=True,
            )

        systems = systems_qs.select_related("site").order_by(
            "system_type", "manufacturer", "model"
        )

        created_sections = 0
        order_counter = 0

        for system in systems:
            category = system.get_maintenance_category()
            if not category:
                # np. Sieci LAN/OPTO, Inny – na razie pomijamy
                continue

            # 2) Szukamy ostatniej sekcji dla TEGO systemu
            last_section = (
                MaintenanceSection.objects
                .filter(system=system, protocol__site=self.site)
                .select_related("protocol")
                .order_by(
                    "-protocol__period_year",
                    "-protocol__period_month",
                    "-protocol__id",
                    "-id",
                )
                .first()
            )

            if last_section:
                # 2a) Kopia sekcji + wszystkich punktów
                new_section = MaintenanceSection.objects.create(
                    protocol=self,
                    system=system,
                    system_type=last_section.system_type,
                    header_name=last_section.header_name,
                    manufacturer=last_section.manufacturer,
                    model=last_section.model,
                    location=last_section.location,
                    section_result=last_section.section_result,
                    section_remarks=last_section.section_remarks,
                    order=order_counter,
                )

                for item in last_section.check_items.all().order_by("order", "id"):
                    MaintenanceCheckItem.objects.create(
                        section=new_section,
                        order=item.order,
                        label=item.label,
                        result=item.result,
                        note=item.note,
                        active=item.active,
                    )

            else:
                # 2b) Brak historii dla tego systemu – tworzymy z domyślnej checklisty
                header = MAINTENANCE_SECTION_HEADERS.get(category)
                checks = MAINTENANCE_DEFAULT_CHECKS.get(category, [])
                if not header or not checks:
                    continue

                new_section = MaintenanceSection.objects.create(
                    protocol=self,
                    system=system,
                    system_type=category,
                    header_name=header,
                    manufacturer=system.manufacturer or "",
                    model=system.model or "",
                    location=system.location_info or "",
                    order=order_counter,
                )

                for idx, label in enumerate(checks, start=1):
                    MaintenanceCheckItem.objects.create(
                        section=new_section,
                        order=idx,
                        label=label,
                    )

            created_sections += 1
            order_counter += 1

        return created_sections
    
    @property
    def period_display(self):
        """Napis typu 02/2025 albo pusty string, jeśli brak danych."""
        if self.period_month and self.period_year:
            return f"{self.period_month:02d}/{self.period_year}"
        return ""

    @property
    def next_period_display(self):
        """Napis typu 05/2025 dla następnego przeglądu."""
        if self.next_period_month and self.next_period_year:
            return f"{self.next_period_month:02d}/{self.next_period_year}"
        return ""
    @property
    def contract_period_bounds(self):
        """
        Zwraca (start_year, start_month, end_year, end_month)
        dla okresu wg umowy, wyliczonego z częstotliwości i miesiąca wykonania.
        """
        site = self.site
        if not site or not self.period_year or not self.period_month:
            return None

        freq = getattr(site, "maintenance_frequency", None)
        exec_year = self.period_year
        exec_month = self.period_month

        # domyślnie traktujemy jako 1 miesiąc (miesięczne, brak danych, custom)
        period_length = 1
        if freq == Site.MaintenanceFrequency.QUARTERLY:
            period_length = 3
        elif freq == Site.MaintenanceFrequency.SEMIANNUAL:
            period_length = 6

        # Który miesiąc okresu jest miesiącem wykonania (1..period_length)
        exec_in_period = getattr(site, "maintenance_execution_month_in_period", 1) or 1
        if exec_in_period < 1:
            exec_in_period = 1
        if exec_in_period > period_length:
            exec_in_period = period_length

        # Przeliczamy na "absolutne" numery miesięcy (rok*12 + (miesiąc-1))
        exec_abs = exec_year * 12 + (exec_month - 1)
        start_abs = exec_abs - (exec_in_period - 1)
        end_abs = start_abs + (period_length - 1)

        start_year = start_abs // 12
        start_month = start_abs % 12 + 1
        end_year = end_abs // 12
        end_month = end_abs % 12 + 1
        return (start_year, start_month, end_year, end_month)

    @property
    def contract_period_display(self):
        """
        Ładny napis typu:
        - '02/2025' (miesięczne),
        - '01/2025-03/2025' (kwartalne/półroczne).
        """
        bounds = self.contract_period_bounds
        if not bounds:
            return ""
        sy, sm, ey, em = bounds
        if sy == ey and sm == em:
            return f"{sm:02d}/{sy}"
        return f"{sm:02d}/{sy}-{em:02d}/{ey}"





class MaintenanceSection(models.Model):
    """Sekcja protokołu konserwacji dla konkretnego systemu na obiekcie."""

    class CheckResult(models.TextChoices):
        OK = "OK", "✓ poprawny"
        FAIL = "FAIL", "X niepoprawny"
        NOT_DONE = "NOT_DONE", "O niewykonany"

    protocol = models.ForeignKey(
        MaintenanceProtocol,
        on_delete=models.CASCADE,
        related_name="sections",
        verbose_name="Protokół konserwacji",
    )

    system = models.ForeignKey(
        System,
        on_delete=models.SET_NULL,
        related_name="maintenance_sections",
        verbose_name="System na obiekcie",
        blank=True,
        null=True,
    )

    system_type = models.CharField(
        "Typ systemu",
        max_length=32,
        blank=True,
        help_text="Cache typu systemu (SSP, CCTV, SSWIN itp.) dla raportów.",
    )

    header_name = models.CharField(
        "Nazwa sekcji",
        max_length=100,
        help_text='Np. "System SSP", "System CCTV".',
    )

    manufacturer = models.CharField(
        "Producent",
        max_length=100,
        blank=True,
    )

    model = models.CharField(
        "Model",
        max_length=100,
        blank=True,
    )

    location = models.CharField(
        "Lokalizacja",
        max_length=255,
        blank=True,
        help_text="Np. portiernia, rozdzielnia, szafa RACK itp.",
    )

    section_result = models.CharField(
        "Wynik sekcji",
        max_length=16,
        choices=CheckResult.choices,
        blank=True,
        null=True,
    )

    section_remarks = models.TextField(
        "Uwagi (podsumowanie sekcji)",
        blank=True,
        help_text="Podsumowanie przeglądu dla całego systemu w tej sekcji.",
    )

    order = models.PositiveIntegerField(
        "Kolejność sekcji",
        default=0,
    )

    class Meta:
        verbose_name = "Sekcja protokołu konserwacji"
        verbose_name_plural = "Sekcje protokołu konserwacji"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.header_name} – {self.location or 'bez lokalizacji'}"


class MaintenanceCheckItem(models.Model):
    """Pojedynczy punkt kontrolny w sekcji protokołu konserwacji."""

    section = models.ForeignKey(
        MaintenanceSection,
        on_delete=models.CASCADE,
        related_name="check_items",
        verbose_name="Sekcja protokołu",
    )

    order = models.PositiveIntegerField(
        "Kolejność w sekcji",
        default=0,
    )

    label = models.CharField(
        "Opis czynności",
        max_length=255,
        help_text="Np. 'Sprawdzenie zasilania centrali'.",
    )

    result = models.CharField(
        "Wynik",
        max_length=16,
        choices=MaintenanceSection.CheckResult.choices,
        default=MaintenanceSection.CheckResult.NOT_DONE,
    )

    note = models.TextField(
        "Tekst własny",
        blank=True,
        help_text="Dopisek pod punktem, np. 'data montażu: 2025/02'.",
    )

    active = models.BooleanField(
        "Aktywny",
        default=True,
        help_text="Czy ten punkt jest używany dla danego obiektu.",
    )

    class Meta:
        verbose_name = "Punkt kontrolny przeglądu"
        verbose_name_plural = "Punkty kontrolne przeglądu"
        ordering = ["order", "id"]

    def __str__(self):
        return self.label
   

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

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Szkic"
        FINAL = "FINAL", "Zatwierdzony"

    work_order = models.OneToOneField(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="service_report",
        verbose_name="Zlecenie",
        help_text="Zlecenie, którego dotyczy ten protokół (typu Serwis).",
    )

    number = models.CharField(
        "Numer protokołu",
        max_length=20,
        blank=True,
        help_text="Jeśli puste, numer zostanie nadany automatycznie przy zatwierdzeniu (PS 01-MM-RRRR).",
    )

    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
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
                {"work_order": "Protokół serwisowy można podpiąć tylko do zlecenia typu 'Serwis'."}
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

        # AUTO NUMERACJA TYLKO DLA ZATWIERDZONYCH (FINAL)
        if (
            self.status == ServiceReport.Status.FINAL
            and not self.number
            and self.report_date
        ):
            year = self.report_date.year
            month = self.report_date.month

            # liczymy tylko protokoły, które JUŻ MAJĄ numer (inne FINAL/DRAFT z pustym numerem ignorujemy)
            count = (
                ServiceReport.objects.filter(
                    report_date__year=year,
                    report_date__month=month,
                )
                .exclude(pk=self.pk)
                .exclude(number__isnull=True)
                .exclude(number__exact="")
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
            full_name = getattr(user, "get_full_name", lambda: "")() or getattr(
                user, "username", ""
            )
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


# ==========================
#  USTAWIENIA KONSERWACJI KS
# ==========================

# Klucze kategorii – będą później mapowane z System.SystemType:
#  - "SSP"
#  - "ODDYM"
#  - "CCTV"
#  - "VIDEODOMOFON"
#  - "KD"
#  - "SSWIN"
#  - "RTV_SAT"

MAINTENANCE_SECTION_HEADERS = {
    "SSP": "System SSP",
    "ODDYM": "System Oddymiania",
    "CCTV": "System CCTV",
    "VIDEODOMOFON": "System Video/Domofonowy",
    "KD": "System Kontroli Dostępu",
    "SSWIN": "System SSWiN",
    "RTV_SAT": "System RTV/SAT",
}

MAINTENANCE_DEFAULT_CHECKS = {
    "SSP": [
        "Sprawdzenie zasilania centrali",
        "Sprawdzenie akumulatora centrali",
        "Sprawdzenie poprawności pracy centrali",
        "Sprawdzenie elementów pętli",
        "Sprawdzenie zadziałania sterowań pętli",
        "Sprawdzenie linii sygnalizacyjnych",
        "Sprawdzenie zasilaczy p-poż",
    ],
    "ODDYM": [
        "Sprawdzenie zasilania centrali",
        "Sprawdzenie akumulatora centrali",
        "Sprawdzenie poprawności pracy centrali",
        "Sprawdzenie elementów liniowych",
        "Sprawdzenie oddymiania",
        "Sprawdzenie napowietrzania",
    ],
    "CCTV": [
        "Sprawdzenie działania systemu",
        "Sprawdzenie elementów systemu",
        "Sprawdzenie długości zapisu",
        "Sprawdzenie odczytu materiału",
        "Wyczyszczono kamery nr",
        "Regulacja kamery nr (jeśli wymagana)",
        "Sprawdzenie łączności sieciowej",
    ],
    "VIDEODOMOFON": [
        "Sprawdzenie zasilania systemu",
        "Sprawdzenie poprawności pracy systemu",
        "Sprawdzenie łączności z losowymi lokalami",
        "Sprawdzenie poprawności działania sterowań",
    ],
    "KD": [
        "Sprawdzenie zasilania systemu",
        "Sprawdzenie poprawności pracy systemu",
        "Sprawdzenie poprawności działania sterowań",
    ],
    "SSWIN": [
        "Sprawdzenie zasilania centrali",
        "Sprawdzenie akumulatora centrali",
        "Sprawdzenie poprawności pracy centrali",
        "Sprawdzenie elementów systemu",
        "Sprawdzenie pamięci zdarzeń za okres",
        "Sprawdzenie modułów i zasilaczy",
    ],
    "RTV_SAT": [
        "Sprawdzenie zasilania systemu",
        "Sprawdzenie poprawności pracy systemu",
        "Sprawdzenie sygnału z anten DVB-T / FM",
        "Sprawdzenie sygnału anten DVB-S",
        "Regulacja anten (jeśli wymagana)",
    ],
}
