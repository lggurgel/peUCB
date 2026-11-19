from datetime import datetime

from django.db import models
from django.utils import timezone

from accounts.models import Profile

MATERIAL_LABELS = {
    "pet": "PET",
    "can": "Lata",
    "glass": "Vidro",
    "cardboard": "Papelão",
    "other": "Outros",
}

STATUS_LABELS = {
    "open": "Aberta",
    "reserved": "Reservada",
    "completed": "Realizada",
    "missed": "Não realizada",
}

KIND_LABELS = {
    "individual": "Pessoa física",
    "company": "Empresa",
}


class CollectionWindow(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESERVED = "reserved", "Reserved"
        COMPLETED = "completed", "Completed"
        MISSED = "missed", "Missed"

    generator = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="windows")
    materials = models.CharField(max_length=80)
    estimated_volume = models.CharField(max_length=120)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    access_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date", "scheduled_time"]

    def __str__(self):
        return f"{self.generator.public_name} {self.scheduled_date} {self.scheduled_time}"

    @property
    def material_list(self):
        return [code for code in self.materials.split(",") if code]

    @property
    def starts_at(self):
        combined = datetime.combine(self.scheduled_date, self.scheduled_time)
        if timezone.is_naive(combined):
            return timezone.make_aware(combined, timezone.get_current_timezone())
        return combined

    @property
    def is_past(self):
        return self.starts_at < timezone.now()


class Agreement(models.Model):
    window = models.OneToOneField(CollectionWindow, on_delete=models.CASCADE, related_name="agreement")
    collector = models.ForeignKey(Profile, on_delete=models.PROTECT, related_name="agreements")
    confirmed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.collector.display_name} -> {self.window_id}"
