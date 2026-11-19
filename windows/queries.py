from collections import Counter

from django.db.models import Q
from django.utils import timezone

from accounts.models import Profile
from windows.models import MATERIAL_LABELS, CollectionWindow


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
    for profile in profiles:
        pins.append(
            {
                "name": profile.public_name,
                "address": profile.address,
                "lat": float(profile.latitude),
                "lng": float(profile.longitude),
                "open_count": counts[profile.id],
                "pending": profile.id in pending_ids,
                "url": f"/windows/?generator={profile.id}",
            }
        )
    return pins
