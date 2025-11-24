from django.db import models

# Create your models here.
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

    def __str__(self):
        return self.name
