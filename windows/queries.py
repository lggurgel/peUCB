from collections import Counter
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from windows.models import MATERIAL_LABELS, STATUS_LABELS, CollectionWindow


def open_windows():
    now = timezone.localtime()
    return (
        CollectionWindow.objects.filter(status=CollectionWindow.Status.OPEN)
        .filter(
            Q(scheduled_date__gt=now.date())
            | Q(scheduled_date=now.date(), scheduled_time__gte=now.time())
        )
        .select_related("generator")
    )


def filter_by_material(queryset, code):
    if code not in MATERIAL_LABELS:
        return queryset
    return queryset.filter(
        Q(materials=code)
        | Q(materials__startswith=f"{code},")
        | Q(materials__endswith=f",{code}")
        | Q(materials__contains=f",{code},")
    )


def generator_pins():
    windows = open_windows()
    counts = Counter(windows.values_list("generator_id", flat=True))
    pending_ids = set(
        CollectionWindow.objects.filter(
            status__in=[CollectionWindow.Status.OPEN, CollectionWindow.Status.RESERVED]
        ).values_list("generator_id", flat=True)
    )
    pins = []
    profiles = Profile.objects.filter(
        role=Profile.Role.GENERATOR,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    home = reverse("home")
    for profile in profiles:
        pins.append(
            {
                "name": profile.public_name,
                "address": profile.address,
                "lat": float(profile.latitude),
                "lng": float(profile.longitude),
                "open_count": counts[profile.id],
                "pending": profile.id in pending_ids,
                "url": f"{home}?generator={profile.id}#janelas",
            }
        )
    return pins


def wait_minutes(delta):
    """Whole minutes in a wait, half a minute rounding up. None when there is no wait."""
    if delta is None or delta < timedelta(0):
        return None
    return int(delta.total_seconds() / 60 + 0.5)


def format_wait(delta):
    """'2 h 40 min' for the time between publication and confirmation."""
    minutes = wait_minutes(delta)
    if minutes is None:
        return ""
    hours, rest = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days} d")
    if hours:
        parts.append(f"{hours} h")
    if rest or not parts:
        parts.append(f"{rest} min")
    return " ".join(parts)


def agreement_of(window):
    """The window's agreement, or None while nobody has confirmed it."""
    return getattr(window, "agreement", None)


def records_summary(windows, generators):
    """Numbers for the review account. `windows` and `generators` are already loaded lists."""
    total = len(windows)
    status_counts = Counter(window.status for window in windows)
    material_counts = Counter(
        code for window in windows for code in window.material_list if code in MATERIAL_LABELS
    )
    waits = [
        agreement.wait
        for agreement in (agreement_of(window) for window in windows)
        if agreement is not None and wait_minutes(agreement.wait) is not None
    ]
    average = sum(waits, timedelta(0)) / len(waits) if waits else None

    def row(key, label, count):
        return {
            "key": key,
            "label": label,
            "count": count,
            "percent": round(100 * count / total) if total else 0,
        }

    completed = status_counts[CollectionWindow.Status.COMPLETED]
    return {
        "total": total,
        "completed": completed,
        "closed": completed + status_counts[CollectionWindow.Status.MISSED],
        "places": len(generators),
        "places_with_windows": sum(1 for place in generators if place.window_count),
        "average_wait": format_wait(average),
        "status_rows": [
            row(status, STATUS_LABELS[status], status_counts[status])
            for status, _label in CollectionWindow.Status.choices
        ],
        "material_rows": [
            row(code, label, material_counts[code]) for code, label in MATERIAL_LABELS.items()
        ],
    }
