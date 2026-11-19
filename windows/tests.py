from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile, User
from windows.models import Agreement, CollectionWindow
from windows.queries import generator_pins
from windows.services import WindowActionError, confirm_window


class ConfirmationRuleTests(TestCase):
    def setUp(self):
        self.generator = self._profile("loja@example.com", Profile.Role.GENERATOR, "Loja Centro")
        self.first = self._profile("ana@example.com", Profile.Role.COLLECTOR, "Ana")
        self.second = self._profile("bruno@example.com", Profile.Role.COLLECTOR, "Bruno")
        when = timezone.localtime() + timedelta(days=2)
        self.window = CollectionWindow.objects.create(
            generator=self.generator,
            materials="pet,can",
            estimated_volume="1 saco",
            scheduled_date=when.date(),
            scheduled_time=when.time().replace(microsecond=0),
        )

    def _profile(self, email, role, name):
        user = User.objects.create_user(email=email, password="demo1234")
        return Profile.objects.create(
            user=user,
            role=role,
            display_name=name,
            organization_name=name if role == Profile.Role.GENERATOR else "",
            collector_kind=Profile.CollectorKind.INDIVIDUAL if role == Profile.Role.COLLECTOR else "",
            address="Rua 1" if role == Profile.Role.GENERATOR else "",
            latitude="-15.800000" if role == Profile.Role.GENERATOR else None,
            longitude="-47.900000" if role == Profile.Role.GENERATOR else None,
            phone="61900000000" if role == Profile.Role.COLLECTOR else "",
        )

    def test_only_the_first_confirmation_reserves_the_window(self):
        confirm_window(self.window.pk, self.first)
        with self.assertRaises(WindowActionError) as caught:
            confirm_window(self.window.pk, self.second)
        self.assertEqual(caught.exception.code, "already_reserved")
        self.window.refresh_from_db()
        self.assertEqual(self.window.status, CollectionWindow.Status.RESERVED)
        self.assertEqual(Agreement.objects.get(window=self.window).collector, self.first)

    def test_generator_cannot_confirm_own_window(self):
        with self.assertRaises(WindowActionError) as caught:
            confirm_window(self.window.pk, self.generator)
        self.assertEqual(caught.exception.code, "not_collector")
        self.assertEqual(CollectionWindow.objects.get(pk=self.window.pk).status, CollectionWindow.Status.OPEN)

    def test_past_window_cannot_be_confirmed(self):
        yesterday = timezone.localtime() - timedelta(days=1)
        self.window.scheduled_date = yesterday.date()
        self.window.scheduled_time = yesterday.time().replace(microsecond=0)
        self.window.save()
        with self.assertRaises(WindowActionError) as caught:
            confirm_window(self.window.pk, self.first)
        self.assertEqual(caught.exception.code, "past")

    def test_second_collector_sees_the_refusal_on_the_page(self):
        confirm_window(self.window.pk, self.first)
        self.client.force_login(self.second.user)
        response = self.client.post(f"/windows/{self.window.pk}/confirm/", follow=True)
        self.assertContains(response, "Esta janela já foi reservada.")
        self.assertNotContains(response, "Ana")
        self.assertNotContains(response, "61900000000")

    def test_parties_see_the_agreement_and_the_phone_stays_hidden(self):
        confirm_window(self.window.pk, self.first)
        self.client.force_login(self.generator.user)
        response = self.client.get(f"/windows/{self.window.pk}/")
        self.assertContains(response, "Ana")
        self.assertNotContains(response, "61900000000")
        self.client.force_login(self.first.user)
        response = self.client.get(f"/windows/{self.window.pk}/")
        self.assertContains(response, "Ana")
        texts = [m.message for m in get_messages(response.wsgi_request)]
        self.assertEqual(texts, [])

    def test_material_filter_matches_a_code_inside_the_list(self):
        response = self.client.get("/windows/?material=can")
        self.assertContains(response, "Loja Centro")
        response = self.client.get("/windows/?material=glass")
        self.assertNotContains(response, "Loja Centro")

    def test_only_the_generator_can_close_a_reserved_window(self):
        confirm_window(self.window.pk, self.first)
        self.client.force_login(self.first.user)
        self.client.post(f"/windows/{self.window.pk}/complete/")
        self.window.refresh_from_db()
        self.assertEqual(self.window.status, CollectionWindow.Status.RESERVED)
        self.client.force_login(self.generator.user)
        self.client.post(f"/windows/{self.window.pk}/complete/")
        self.window.refresh_from_db()
        self.assertEqual(self.window.status, CollectionWindow.Status.COMPLETED)


class PilotSeedTests(TestCase):
    def test_seed_records_lucas_collecting_the_day_after_publication(self):
        call_command("seed_demo")
        call_command("seed_demo")
        window = CollectionWindow.objects.get(scheduled_date=date(2026, 11, 8), scheduled_time=time(10, 0))
        self.assertEqual(CollectionWindow.objects.filter(scheduled_date=date(2026, 11, 8)).count(), 1)
        self.assertEqual(window.status, CollectionWindow.Status.COMPLETED)
        published = timezone.localtime(window.created_at)
        confirmed = timezone.localtime(window.agreement.confirmed_at)
        self.assertEqual((published.year, published.month, published.day, published.hour, published.minute), (2026, 11, 7, 16, 0))
        self.assertEqual((confirmed.year, confirmed.month, confirmed.day, confirmed.hour, confirmed.minute), (2026, 11, 7, 18, 40))
        self.assertEqual(window.agreement.collector.display_name, "Lucas Gabriel de Oliveira Gurgel")
        self.assertFalse(User.objects.filter(email="coletador@example.com").exists())

        second = CollectionWindow.objects.get(scheduled_date=date(2026, 11, 18), scheduled_time=time(9, 0))
        self.assertEqual(second.status, CollectionWindow.Status.COMPLETED)
        self.assertEqual(second.estimated_volume, "cerca de 2 sacos")
        self.assertEqual(second.agreement.collector, window.agreement.collector)
        published = timezone.localtime(second.created_at)
        confirmed = timezone.localtime(second.agreement.confirmed_at)
        self.assertEqual((published.year, published.month, published.day, published.hour, published.minute), (2026, 11, 17, 11, 20))
        self.assertEqual((confirmed.year, confirmed.month, confirmed.day, confirmed.hour, confirmed.minute), (2026, 11, 17, 14, 5))

        visit = User.objects.get(email="bistrozin.visita@example.com")
        self.assertFalse(visit.has_usable_password())
        self.assertEqual(visit.profile.organization_name, "Bistrozin")
        self.assertEqual(visit.profile.windows.count(), 0)

        home = self.client.get("/")
        self.assertContains(home, "Coleta realizada")
        self.assertContains(home, "Publicada em 07/11/2026 às 16:00")
        self.assertContains(home, "Coleta em 08/11/2026 às 10:00")
        self.assertContains(home, "Publicada em 17/11/2026 às 11:20")
        self.assertContains(home, "Coleta em 18/11/2026 às 09:00")
        self.assertContains(home, "Bistrozin")
        self.assertContains(home, "Realizada")
        self.assertNotContains(home, "Lucas")
        self.assertNotContains(home, "98636")
        self.assertNotContains(home, "Pendência")
        pins = {pin["name"]: pin for pin in generator_pins()}
        self.assertEqual(set(pins), {
            "Informal Distribuidora de Bebidas e Conveniência",
            "Bistrozin",
        })
        informal_pin = pins["Informal Distribuidora de Bebidas e Conveniência"]
        self.assertFalse(informal_pin["pending"])
        self.assertAlmostEqual(informal_pin["lat"], -15.838950, places=5)
        self.assertAlmostEqual(informal_pin["lng"], -48.024180, places=5)
        self.assertFalse(pins["Bistrozin"]["pending"])
        self.assertContains(home, '"pending": false')

        lucas = User.objects.get(email="lucas.gurgel@a.ucb.br")
        self.assertTrue(lucas.check_password("janela2026"))
        self.client.force_login(lucas)
        detail = self.client.get(f"/windows/{window.pk}/")
        self.assertContains(detail, "Lucas Gabriel de Oliveira Gurgel")
        self.assertContains(detail, "07/11/2026 às 18:40")
        self.assertNotContains(detail, "98636")
        mine = self.client.get("/windows/mine/")
        self.assertContains(mine, "Coleta em 08/11/2026 às 10:00")

        self.client.logout()
        anonymous = self.client.get(f"/windows/{window.pk}/")
        self.assertNotContains(anonymous, "Lucas")
        self.assertContains(anonymous, "Publicada em")
        self.client.force_login(lucas)
        refused = self.client.get("/windows/records/", follow=True)
        self.assertContains(refused, "Os registros completos ficam na conta de acompanhamento.")
        self.assertNotContains(refused, "98636")

        reviewer = User.objects.get(email="acompanhamento@example.com")
        self.assertTrue(reviewer.check_password("extensao2026"))
        self.client.force_login(reviewer)
        detail = self.client.get(f"/windows/{window.pk}/")
        self.assertContains(detail, "Lucas Gabriel de Oliveira Gurgel")
        self.assertNotContains(detail, "98636")
        records = self.client.get("/windows/records/")
        self.assertContains(records, "Lucas Gabriel de Oliveira Gurgel")
        self.assertContains(records, "cerca de 3 sacos")
        self.assertContains(records, "cerca de 2 sacos")
        self.assertContains(records, "Bistrozin")
        self.assertContains(records, "só o cadastro, sem janela")
        self.assertContains(records, "07/11/2026 às 18:40")
        self.assertContains(records, "17/11/2026 às 14:05")
        self.assertNotContains(records, "98636")
        self.assertNotContains(records, "bistrozin.visita@example.com")
        profile = self.client.get("/accounts/profile/")
        self.assertContains(profile, "acompanhamento")
        self.assertNotContains(profile, "Telefone")

    def test_pin_is_pending_only_while_a_window_is_still_open_or_reserved(self):
        call_command("seed_demo")
        informal = Profile.objects.get(user__email="informal@example.com")

        def pending(name):
            return {pin["name"]: pin["pending"] for pin in generator_pins()}[name]

        self.assertFalse(pending("Informal Distribuidora de Bebidas e Conveniência"))
        self.assertFalse(pending("Bistrozin"))
        extra = CollectionWindow.objects.create(
            generator=informal,
            materials="pet",
            estimated_volume="1 saco",
            scheduled_date=date(2026, 11, 20),
            scheduled_time=time(9, 0),
            status=CollectionWindow.Status.OPEN,
        )
        self.assertTrue(pending("Informal Distribuidora de Bebidas e Conveniência"))
        self.assertFalse(pending("Bistrozin"))
        extra.status = CollectionWindow.Status.RESERVED
        extra.save(update_fields=["status"])
        Agreement.objects.create(
            window=extra,
            collector=Profile.objects.get(user__email="lucas.gurgel@a.ucb.br"),
        )
        self.assertTrue(pending("Informal Distribuidora de Bebidas e Conveniência"))
        extra.status = CollectionWindow.Status.COMPLETED
        extra.save(update_fields=["status"])
        self.assertFalse(pending("Informal Distribuidora de Bebidas e Conveniência"))
        self.assertFalse(pending("Bistrozin"))

    def test_seed_replaces_only_the_old_informal_pin(self):
        call_command("seed_demo")
        informal = Profile.objects.get(user__email="informal@example.com")
        informal.latitude = "-15.833500"
        informal.longitude = "-48.025600"
        informal.save(update_fields=["latitude", "longitude"])
        call_command("seed_demo")
        informal.refresh_from_db()
        self.assertEqual(informal.latitude, Decimal("-15.838950"))
        self.assertEqual(informal.longitude, Decimal("-48.024180"))

        informal.latitude = "-15.840000"
        informal.longitude = "-48.020000"
        informal.save(update_fields=["latitude", "longitude"])
        call_command("seed_demo")
        informal.refresh_from_db()
        self.assertEqual(informal.latitude, Decimal("-15.840000"))
        self.assertEqual(informal.longitude, Decimal("-48.020000"))
