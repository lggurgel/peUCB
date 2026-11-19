from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db.models import Q

from accounts.models import Profile, User
from windows.models import Agreement, CollectionWindow

INFORMAL_PASSWORD = "demo1234"
LUCAS_PASSWORD = "janela2026"
REVIEWER_PASSWORD = "extensao2026"
GENERATOR_EMAIL = "informal@example.com"
LUCAS_EMAIL = "lucas.gurgel@a.ucb.br"
REVIEWER_EMAIL = "acompanhamento@example.com"
BISTROZIN_EMAIL = "bistrozin.visita@example.com"
OLD_DEMO_COLLECTOR_EMAIL = "coletador@example.com"
# Approximate pin for Rua 19 Norte, Águas Claras. The generator can drag it in the profile.
INFORMAL_LAT = "-15.833500"
INFORMAL_LNG = "-48.025600"
# Approximate pin for Rua 24 Norte, lote 13, loja 6, near Águas Claras station.
BISTROZIN_LAT = "-15.838450"
BISTROZIN_LNG = "-48.028650"
TZ = ZoneInfo("America/Sao_Paulo")


def at(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=TZ)


WEEK7_PUBLISHED = at(2026, 11, 7, 16, 0)
WEEK7_CONFIRMED = at(2026, 11, 7, 18, 40)
WEEK7_COLLECTED = at(2026, 11, 8, 10, 0)
WEEK8_PUBLISHED = at(2026, 11, 17, 11, 20)
WEEK8_CONFIRMED = at(2026, 11, 17, 14, 5)
WEEK8_COLLECTED = at(2026, 11, 18, 9, 0)


class Command(BaseCommand):
    help = "Create the pilot history through 19/11/2026, the visit registration, and the review account."

    def handle(self, *args, **options):
        generator = self._profile(
            email=GENERATOR_EMAIL,
            password=INFORMAL_PASSWORD,
            display_name="Francisca Gomes de Oliveira",
            role=Profile.Role.GENERATOR,
            organization_name="Informal Distribuidora de Bebidas e Conveniência",
            address="Rua 19 Norte, Lotes 06 e 08, Loja 13, Águas Claras, Brasília-DF",
            latitude=INFORMAL_LAT,
            longitude=INFORMAL_LNG,
        )
        lucas = self._profile(
            email=LUCAS_EMAIL,
            password=LUCAS_PASSWORD,
            display_name="Lucas Gabriel de Oliveira Gurgel",
            role=Profile.Role.COLLECTOR,
            collector_kind=Profile.CollectorKind.INDIVIDUAL,
            phone="(61) 98636-4324",
        )
        self._profile(
            email=REVIEWER_EMAIL,
            password=REVIEWER_PASSWORD,
            display_name="Acompanhamento acadêmico",
            role=Profile.Role.REVIEWER,
        )
        # Visit only. No window, and no password, so the place stays a map pin.
        self._profile(
            email=BISTROZIN_EMAIL,
            display_name="Cadastro de visita",
            role=Profile.Role.GENERATOR,
            usable_password=False,
            organization_name="Bistrozin",
            address="Rua 24 Norte, Lote 13, Loja 6, Águas Claras, Brasília-DF",
            latitude=BISTROZIN_LAT,
            longitude=BISTROZIN_LNG,
        )
        self._remove_old_demo()
        self._completed(
            generator,
            lucas,
            published=WEEK7_PUBLISHED,
            confirmed=WEEK7_CONFIRMED,
            collected=WEEK7_COLLECTED,
            volume="cerca de 3 sacos",
            notes="Entrada pela loja 13.",
        )
        self._completed(
            generator,
            lucas,
            published=WEEK8_PUBLISHED,
            confirmed=WEEK8_CONFIRMED,
            collected=WEEK8_COLLECTED,
            volume="cerca de 2 sacos",
            notes="Entrada pela loja 13. Material separado do orgânico.",
        )
        self.stdout.write("Base até 19/11/2026 gravada.")

    def _completed(self, generator, collector, *, published, confirmed, collected, volume, notes):
        window = CollectionWindow.objects.filter(
            generator=generator,
            scheduled_date=collected.date(),
            scheduled_time=collected.time(),
        ).first()
        if window is None:
            window = CollectionWindow.objects.create(
                generator=generator,
                materials="pet,can,glass,cardboard",
                estimated_volume=volume,
                scheduled_date=collected.date(),
                scheduled_time=collected.time(),
                access_notes=notes,
                status=CollectionWindow.Status.COMPLETED,
            )
        CollectionWindow.objects.filter(pk=window.pk).update(
            materials="pet,can,glass,cardboard",
            estimated_volume=volume,
            access_notes=notes,
            status=CollectionWindow.Status.COMPLETED,
            created_at=published,
        )
        agreement = Agreement.objects.filter(window=window).first()
        if agreement is None:
            agreement = Agreement.objects.create(window=window, collector=collector)
        elif agreement.collector_id != collector.id:
            agreement.collector = collector
            agreement.save(update_fields=["collector"])
        Agreement.objects.filter(pk=agreement.pk).update(confirmed_at=confirmed)

    def _remove_old_demo(self):
        # Only the retired demo account is removed. Volume text is not a key:
        # deleting by it would erase a real collection on every restart.
        demo = User.objects.filter(email=OLD_DEMO_COLLECTOR_EMAIL).first()
        if demo is None:
            return
        profile = getattr(demo, "profile", None)
        if profile is not None:
            window_ids = list(
                Agreement.objects.filter(collector=profile).values_list("window_id", flat=True)
            )
            Agreement.objects.filter(collector=profile).delete()
            keep = Q()
            for day, clock in (
                (WEEK7_COLLECTED.date(), WEEK7_COLLECTED.time()),
                (WEEK8_COLLECTED.date(), WEEK8_COLLECTED.time()),
            ):
                keep |= Q(scheduled_date=day, scheduled_time=clock)
            CollectionWindow.objects.filter(pk__in=window_ids).exclude(keep).delete()
        demo.delete()

    def _profile(self, email, password=None, display_name="", role=Profile.Role.GENERATOR, usable_password=True, **fields):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password or "unused-password")
            if not usable_password:
                user.set_unusable_password()
                user.save(update_fields=["password"])
        profile = Profile.objects.filter(user=user).first()
        if profile is None:
            return Profile.objects.create(
                user=user,
                role=role,
                display_name=display_name,
                **fields,
            )
        if not profile.display_name:
            profile.display_name = display_name
        for name, value in fields.items():
            current = getattr(profile, name)
            if current in (None, ""):
                setattr(profile, name, value)
        profile.save()
        return profile
