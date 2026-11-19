from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from accounts.models import Profile, User
from windows.models import Agreement, CollectionWindow

INFORMAL_PASSWORD = "demo1234"
LUCAS_PASSWORD = "janela2026"
GENERATOR_EMAIL = "informal@example.com"
LUCAS_EMAIL = "lucas.gurgel@a.ucb.br"
OLD_DEMO_COLLECTOR_EMAIL = "coletador@example.com"
# Approximate pin for Rua 19 Norte, Águas Claras. The generator can drag it in the profile.
INFORMAL_LAT = "-15.833500"
INFORMAL_LNG = "-48.025600"
TZ = ZoneInfo("America/Sao_Paulo")


def at(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=TZ)


PUBLISHED_AT = at(2026, 11, 7, 16, 0)
CONFIRMED_AT = at(2026, 11, 7, 18, 40)
COLLECTED_ON = at(2026, 11, 8, 10, 0)


class Command(BaseCommand):
    help = "Create Informal, Lucas as collector, and the completed pilot window."

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
        self._remove_old_demo(generator)
        self._pilot(generator, lucas)
        self.stdout.write("Piloto de 07 e 08/11/2026 gravado.")

    def _pilot(self, generator, lucas):
        window = CollectionWindow.objects.filter(
            generator=generator,
            scheduled_date=COLLECTED_ON.date(),
            scheduled_time=COLLECTED_ON.time(),
        ).first()
        if window is None:
            window = CollectionWindow.objects.create(
                generator=generator,
                materials="pet,can,glass,cardboard",
                estimated_volume="cerca de 3 sacos",
                scheduled_date=COLLECTED_ON.date(),
                scheduled_time=COLLECTED_ON.time(),
                access_notes="Entrada pela loja 13.",
                status=CollectionWindow.Status.COMPLETED,
            )
        CollectionWindow.objects.filter(pk=window.pk).update(
            materials="pet,can,glass,cardboard",
            estimated_volume="cerca de 3 sacos",
            access_notes="Entrada pela loja 13.",
            status=CollectionWindow.Status.COMPLETED,
            created_at=PUBLISHED_AT,
        )
        agreement = Agreement.objects.filter(window=window).first()
        if agreement is None:
            agreement = Agreement.objects.create(window=window, collector=lucas)
        elif agreement.collector_id != lucas.id:
            agreement.collector = lucas
            agreement.save(update_fields=["collector"])
        Agreement.objects.filter(pk=agreement.pk).update(confirmed_at=CONFIRMED_AT)

    def _remove_old_demo(self, generator):
        CollectionWindow.objects.filter(
            generator=generator,
            estimated_volume="cerca de 2 sacos",
        ).delete()
        CollectionWindow.objects.filter(estimated_volume="1 fardo").delete()
        demo = User.objects.filter(email=OLD_DEMO_COLLECTOR_EMAIL).first()
        if demo is None:
            return
        profile = getattr(demo, "profile", None)
        if profile is not None:
            window_ids = list(
                Agreement.objects.filter(collector=profile).values_list("window_id", flat=True)
            )
            Agreement.objects.filter(collector=profile).delete()
            CollectionWindow.objects.filter(pk__in=window_ids).exclude(
                scheduled_date=COLLECTED_ON.date(),
                scheduled_time=COLLECTED_ON.time(),
            ).delete()
        demo.delete()

    def _profile(self, email, password, display_name, role, **fields):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password)
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
