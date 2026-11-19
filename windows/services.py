from django.db import IntegrityError, transaction

from accounts.models import Profile
from windows.models import Agreement, CollectionWindow


class WindowActionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def confirm_window(window_id, collector_profile):
    """First valid confirmation reserves the window. Later attempts do not."""
    if collector_profile.role != Profile.Role.COLLECTOR:
        raise WindowActionError("not_collector")

    with transaction.atomic():
        window = CollectionWindow.objects.select_for_update().get(pk=window_id)
        if window.generator_id == collector_profile.id:
            raise WindowActionError("own_window")
        if window.is_past:
            raise WindowActionError("past")
        if window.status != CollectionWindow.Status.OPEN:
            raise WindowActionError("already_reserved")
        try:
            Agreement.objects.create(window=window, collector=collector_profile)
        except IntegrityError as exc:
            raise WindowActionError("already_reserved") from exc
        window.status = CollectionWindow.Status.RESERVED
        window.save(update_fields=["status"])
    return window


def close_window(window_id, generator_profile, outcome):
    if generator_profile.role != Profile.Role.GENERATOR:
        raise WindowActionError("not_generator")
    if outcome not in {CollectionWindow.Status.COMPLETED, CollectionWindow.Status.MISSED}:
        raise WindowActionError("bad_outcome")

    with transaction.atomic():
        window = CollectionWindow.objects.select_for_update().get(pk=window_id)
        if window.generator_id != generator_profile.id:
            raise WindowActionError("not_owner")
        if window.status != CollectionWindow.Status.RESERVED:
            raise WindowActionError("not_reserved")
        window.status = outcome
        window.save(update_fields=["status"])
    return window


def can_see_agreement(profile, window):
    if profile is None:
        return False
    agreement = Agreement.objects.filter(window=window).first()
    if agreement is None:
        return False
    if profile.is_reviewer:
        return True
    return profile.id in {window.generator_id, agreement.collector_id}
