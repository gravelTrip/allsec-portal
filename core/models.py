from django.db import models


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
        "Nazwa / opis systemu",
        max_length=255,
        help_text="Np. 'CCTV garaż + wejścia', 'SSP budynek A+B'.",
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
        return f"{self.name} [{self.get_system_type_display()}] – {self.site}"
