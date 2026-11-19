from django import forms
from django.utils import timezone

from windows.models import MATERIAL_LABELS, CollectionWindow


class WindowForm(forms.ModelForm):
    materials = forms.MultipleChoiceField(
        label="Materiais",
        choices=list(MATERIAL_LABELS.items()),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = CollectionWindow
        fields = ["estimated_volume", "scheduled_date", "scheduled_time", "access_notes"]
        labels = {
            "estimated_volume": "Volume estimado",
            "scheduled_date": "Data",
            "scheduled_time": "Hora",
            "access_notes": "Observação de acesso (opcional)",
        }
        widgets = {
            "scheduled_date": forms.DateInput(attrs={"type": "date"}),
            "scheduled_time": forms.TimeInput(attrs={"type": "time"}),
            "estimated_volume": forms.TextInput(attrs={"placeholder": "Ex.: 2 sacos, cerca de 40 latas"}),
            "access_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        scheduled_date = cleaned.get("scheduled_date")
        scheduled_time = cleaned.get("scheduled_time")
        if scheduled_date and scheduled_time:
            window = CollectionWindow(
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                materials="pet",
                estimated_volume="x",
            )
            if window.starts_at <= timezone.now():
                self.add_error("scheduled_date", "Escolha um dia e horário que ainda não passaram.")
        return cleaned

    def save(self, generator, commit=True):
        window = super().save(commit=False)
        window.generator = generator
        window.materials = ",".join(self.cleaned_data["materials"])
        window.status = CollectionWindow.Status.OPEN
        if commit:
            window.save()
        return window
