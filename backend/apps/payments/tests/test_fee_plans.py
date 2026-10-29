"""Two schools for the price of one, a 3rd for 100,000 more, and pay small small.

The rules (David, October 2026):
  * one application fee (the 1st choice school's own) covers a 1st and 2nd choice;
  * a 3rd choice adds 100,000 Naira;
  * pay small small: 100,000 deposit, then the rest in two equal weekly parts;
  * work starts once the deposit is in; the agent's commission (and the sales
    manager's bonus) only once everything is paid, once per fee;
  * a missed instalment only brings reminders.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Application, ApplicationDraft, ApplicationDraftFile
from apps.applications.tests.factories import make_user
from apps.catalog.models import DestinationCountry, Institution, OriginCountry, Program
from apps.partners.models import AgentProfile, Commission, SupervisorBonus, SupervisorProfile, Wallet
from apps.payments import plans
from apps.payments.fees import minor_units
from apps.payments.models import Payment, PaymentCharge
from apps.payments.views import quote_for

KEY = "sk_test_simulated"
NGN = Decimal


def paystack_answer(path, payload=None, method="GET"):
    """A Paystack that always opens a checkout page."""
    return {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/x"}}


@override_settings(PAYSTACK_SECRET_KEY=KEY)
class FeePlanTests(TestCase):
    def setUp(self):
        cache.clear()
        OriginCountry.objects.update_or_create(
            name="Nigeria", defaults={"currency": "NGN", "symbol": "₦", "ngn_per_unit": NGN("1")}
        )
        canada = DestinationCountry.objects.update_or_create(name="Canada", defaults={"code": "CA", "currency": "CAD"})[0]
        # Three schools whose fee is 200,000 Naira, so the sums are plain.
        self.schools = []
        for slug in ("maple", "oak", "pine"):
            school = Institution.objects.create(
                slug=slug, name=slug.title() + " College", country=canada,
                application_fee=NGN("200000"), application_fee_currency="NGN", currency="CAD",
            )
            course = Program.objects.create(institution=school, name=f"{slug.title()} Nursing")
            self.schools.append((school, course))
        self.applicant = make_user("ada@example.com", full_name="Ada Lovelace", country="Nigeria")
        self.client = APIClient()
        self.client.force_authenticate(self.applicant)
        self.call = mock.patch("apps.payments.gateway._call", side_effect=paystack_answer).start()
        self.addCleanup(mock.patch.stopall)

    # ── helpers ──

    def payload(self, extra=0):
        first, course = self.schools[0]
        body = {
            "full_name": "Ada Lovelace", "email": "ada@example.com", "phone": "+2348000000000",
            "origin_country": "Nigeria", "destination_country": "Canada", "previous_schools": "School",
            "qualification": "BSc", "year_graduated": 2020, "grade_gpa": "4.0",
            "institution": first.slug, "program_ids": [course.id],
            "extra_choices": [
                {"institution": school.slug, "program_ids": [course.id]} for school, course in self.schools[1 : 1 + extra]
            ],
        }
        return body

    def apply(self, extra=1, client=None, url="/api/applications/"):
        response = (client or self.client).post(url, self.payload(extra), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return Application.objects.get(reference=response.json()["reference"])

    def checkout(self, application, **extra):
        return self.client.post(
            "/api/payments/checkout/", {"application": application.reference, **extra}, format="json"
        )

    def webhook(self, payment, reference, amount_ngn):
        body = json.dumps({
            "event": "charge.success",
            "data": {"reference": reference, "status": "success", "currency": "NGN", "amount": minor_units(amount_ngn)},
        }).encode()
        signature = hmac.new(KEY.encode(), body, hashlib.sha512).hexdigest()
        APIClient().post(
            "/api/payments/webhook/paystack/", body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=signature
        )

    def pay_open_charge(self, application):
        """Complete the charge the last checkout opened."""
        payment = Payment.objects.get(application=application.fee_owner)
        charge = payment.charges.filter(status="pending").order_by("-created_at", "-pk").first()
        self.webhook(payment, charge.gateway_reference, charge.expected_ngn)
        payment.refresh_from_db()
        return payment, charge

    # ── two schools for the price of one ──

    def test_a_second_choice_is_its_own_file_under_the_same_fee(self):
        first = self.apply(extra=1)
        second = first.covered_applications.get()
        self.assertEqual((second.choice_order, second.fee_parent_id), (2, first.pk))
        self.assertEqual(second.institution, self.schools[1][0])
        self.assertEqual(list(second.programs.all()), [self.schools[1][1]])
        self.assertEqual(second.stages.count(), first.stages.count())
        self.assertEqual(quote_for(first)["amount_ngn"], NGN("200000.00"))
        self.assertEqual(quote_for(second)["amount_ngn"], NGN("200000.00"))
        self.assertEqual(quote_for(second)["fee_reference"], first.reference)

    def test_a_third_choice_adds_one_hundred_thousand(self):
        first = self.apply(extra=2)
        self.assertEqual(first.covered_applications.count(), 2)
        quote = quote_for(first)
        self.assertEqual(quote["amount_ngn"], NGN("300000.00"))
        self.assertEqual(quote["extra_school_ngn"], NGN("100000.00"))
        self.assertEqual([row["amount_ngn"] for row in quote["instalments"]], [NGN("100000")] * 3)

    def test_the_fee_is_the_first_choice_schools_own(self):
        dear = self.schools[0][0]
        dear.application_fee = NGN("250000")
        dear.save()
        first = self.apply(extra=1)
        self.assertEqual(quote_for(first)["amount_ngn"], NGN("250000.00"))
        self.assertEqual(plans.instalment_amounts(NGN("250000")), [NGN("100000"), NGN("75000.00"), NGN("75000.00")])

    def test_a_fee_free_first_choice_cannot_make_the_others_free(self):
        free = self.schools[0][0]
        free.application_fee = NGN("0")
        free.save()
        first = self.apply(extra=1)
        self.assertEqual(quote_for(first)["amount_ngn"], NGN("200000.00"))

    def test_choices_must_be_different_real_schools_and_courses(self):
        body = self.payload(1)
        body["extra_choices"] = [{"institution": self.schools[0][0].slug, "program_ids": [self.schools[0][1].id]}]
        self.assertEqual(self.client.post("/api/applications/", body, format="json").status_code, 400)
        body["extra_choices"] = [{"institution": self.schools[1][0].slug, "program_ids": [self.schools[2][1].id]}]
        self.assertEqual(self.client.post("/api/applications/", body, format="json").status_code, 400)
        body["extra_choices"] = [{"institution": "nowhere", "program_ids": [1]}]
        self.assertEqual(self.client.post("/api/applications/", body, format="json").status_code, 400)
        body = self.payload(2)
        body["extra_choices"].append({"institution": "x", "program_ids": [1]})
        self.assertEqual(self.client.post("/api/applications/", body, format="json").status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_a_school_already_applied_to_cannot_be_a_second_choice(self):
        self.apply(extra=0)
        body = self.payload(0)
        body["institution"], body["program_ids"] = self.schools[1][0].slug, [self.schools[1][1].id]
        body["extra_choices"] = [{"institution": self.schools[0][0].slug, "program_ids": [self.schools[0][1].id]}]
        response = self.client.post("/api/applications/", body, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Application.objects.count(), 1)

    def test_draft_documents_go_on_every_schools_file(self):
        draft = ApplicationDraft.objects.create(user=self.applicant)
        ApplicationDraftFile.objects.create(
            draft=draft, slot="passport", kind="passport", name="Passport",
            file=ContentFile(b"%PDF-1.4 x", name="passport.pdf"),
        )
        first = self.apply(extra=2)
        for app in [first, *first.covered_applications.all()]:
            self.assertEqual(app.documents.count(), 1, app.reference)

    # ── paying in full ──

    def test_paying_in_full_pays_for_every_school(self):
        first = self.apply(extra=1)
        second = first.covered_applications.get()
        response = self.checkout(second)  # from the 2nd choice: charged on the 1st
        self.assertEqual(response.status_code, 201, response.content)
        payment, charge = self.pay_open_charge(first)
        self.assertEqual(charge.amount_ngn, NGN("200000"))
        self.assertEqual((payment.status, payment.paid_ngn), (Payment.Status.PAID, NGN("200000")))
        for app in (first, second):
            app.refresh_from_db()
            self.assertTrue(app.payment_verified, app.reference)
        self.assertFalse(Payment.objects.filter(application=second).exists())

    # ── pay small small ──

    def test_deposit_then_instalments_and_commission_only_at_the_end(self):
        agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        manager = SupervisorProfile.objects.create(user=make_user("mgr@example.com", role=User.Role.SUPERVISOR))
        agent = AgentProfile.objects.create(user=agent_user, supervisor=manager)
        Wallet.objects.create(agent=agent)
        agent_client = APIClient()
        agent_client.force_authenticate(agent_user)
        self.client = agent_client
        body = self.payload(1)
        body["email"] = "student@example.com"
        response = agent_client.post("/api/partners/students/", body, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        first = Application.objects.get(reference=response.json()["reference"])
        second = first.covered_applications.get()

        # Deposit.
        self.assertEqual(self.checkout(first, plan="instalments", return_to="agent").status_code, 201)
        payment, charge = self.pay_open_charge(first)
        self.assertEqual((charge.kind, charge.amount_ngn), ("deposit", NGN("100000")))
        self.assertEqual(payment.status, Payment.Status.PART_PAID)
        self.assertEqual(payment.balance_ngn, NGN("100000"))
        self.assertIsNotNone(payment.deposit_paid_at)
        for app in (first, second):
            app.refresh_from_db()
            self.assertTrue(app.payment_verified)  # work starts
        self.assertFalse(Commission.objects.exists())  # not yet
        self.assertFalse(SupervisorBonus.objects.exists())
        upcoming = plans.next_instalment(payment)
        self.assertEqual(upcoming["amount_ngn"], NGN("50000"))
        self.assertEqual(upcoming["due_on"], (payment.deposit_paid_at + timedelta(days=7)).date())

        # The agent's Students table says where it stands.
        row = next(r for r in agent_client.get("/api/partners/students/").json() if r["reference"] == second.reference)
        self.assertEqual(row["fee_status"], "part_paid")
        self.assertEqual(row["fee_display"], "₦100,000 of ₦200,000")

        # Second instalment.
        self.assertEqual(self.checkout(first, pay="next", return_to="agent").status_code, 201)
        payment, charge = self.pay_open_charge(first)
        self.assertEqual((charge.kind, charge.amount_ngn), ("instalment", NGN("50000")))
        self.assertEqual((payment.status, payment.paid_ngn), (Payment.Status.PART_PAID, NGN("150000")))
        self.assertFalse(Commission.objects.exists())

        # The balance at once.
        self.assertEqual(self.checkout(first, pay="balance", return_to="agent").status_code, 201)
        payment, charge = self.pay_open_charge(first)
        self.assertEqual((charge.kind, charge.amount_ngn), ("balance", NGN("50000")))
        self.assertEqual(payment.status, Payment.Status.PAID)
        # One commission and one bonus for the fee, not one per school.
        self.assertEqual(Commission.objects.filter(kind="registration").count(), 1)
        self.assertEqual(SupervisorBonus.objects.count(), 1)
        self.assertEqual(self.checkout(first).json().get("already_settled"), True)

    def test_a_repeated_webhook_is_counted_once(self):
        first = self.apply(extra=1)
        self.checkout(first, plan="instalments")
        payment = Payment.objects.get(application=first)
        charge = payment.charges.get()
        self.webhook(payment, charge.gateway_reference, charge.expected_ngn)
        self.webhook(payment, charge.gateway_reference, charge.expected_ngn)
        payment.refresh_from_db()
        self.assertEqual(payment.paid_ngn, NGN("100000"))

    def test_a_short_payment_is_not_counted(self):
        first = self.apply(extra=1)
        self.checkout(first, plan="instalments")
        payment = Payment.objects.get(application=first)
        charge = payment.charges.get()
        self.webhook(payment, charge.gateway_reference, NGN("40000"))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.paid_ngn), (Payment.Status.PENDING, NGN("0")))

    def test_an_abandoned_attempt_completed_later_is_still_counted_at_its_amount(self):
        first = self.apply(extra=1)
        self.checkout(first, plan="instalments")
        payment = Payment.objects.get(application=first)
        abandoned = payment.charges.get()
        self.checkout(first, plan="instalments")  # opens again, pays this one
        payment, _ = self.pay_open_charge(first)
        self.assertEqual(payment.paid_ngn, NGN("100000"))
        # The first tab is completed too: the money is real, so it counts.
        self.webhook(payment, abandoned.gateway_reference, abandoned.expected_ngn)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.paid_ngn), (Payment.Status.PAID, NGN("200000")))

    def test_the_plan_cannot_change_once_money_is_in(self):
        first = self.apply(extra=1)
        self.checkout(first, plan="instalments")
        self.pay_open_charge(first)
        self.checkout(first, plan="full")  # means: pay what is left
        payment = Payment.objects.get(application=first)
        charge = payment.charges.filter(status="pending").get()
        self.assertEqual((payment.plan, charge.amount_ngn), ("instalments", NGN("100000")))

    # ── by bank transfer ──

    def transfer(self, application, **extra):
        from django.core.files.uploadedfile import SimpleUploadedFile

        receipt = SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 receipt", content_type="application/pdf")
        return self.client.post(
            f"/api/payments/transfer/{application.reference}/", {"bank": "keystone", "receipt": receipt, **extra},
            format="multipart",
        )

    def test_an_instalment_by_transfer_is_confirmed_by_the_desk(self):
        first = self.apply(extra=1)
        self.assertEqual(self.transfer(first, plan="instalments").status_code, 201)
        payment = Payment.objects.get(application=first)
        self.assertEqual(payment.status, Payment.Status.REVIEW)
        self.assertEqual(payment.charges.get().amount_ngn, NGN("100000"))

        staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        desk = APIClient()
        desk.force_login(staff)
        desk.post(reverse("admin:payments_paymenttoconfirm_confirm", args=[payment.pk]))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.paid_ngn), (Payment.Status.PART_PAID, NGN("100000")))

        # The next one by transfer, turned down: back to part paid, nothing counted.
        self.assertEqual(self.transfer(first).status_code, 201)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REVIEW)
        desk.post(reverse("admin:payments_paymenttoconfirm_reject", args=[payment.pk]), {"note": "Not received."})
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.paid_ngn), (Payment.Status.PART_PAID, NGN("100000")))
        self.assertTrue(payment.charges.filter(status="failed").exists())

    # ── reminders ──

    def test_reminders_before_on_and_after_the_due_date_once_each(self):
        first = self.apply(extra=1)
        self.checkout(first, plan="instalments")
        payment, _ = self.pay_open_charge(first)
        due = plans.next_instalment(payment)["due_on"]

        def run(on):
            with mock.patch("django.utils.timezone.localdate", return_value=on):
                call_command("send_fee_reminders", stdout=StringIO())
            payment.refresh_from_db()
            return list(payment.reminders_sent)

        self.assertEqual(run(due - timedelta(days=5)), [])
        self.assertEqual(run(due - timedelta(days=2)), ["2:before"])
        self.assertEqual(run(due - timedelta(days=1)), ["2:before"])  # not twice
        self.assertEqual(run(due), ["2:before", "2:due"])
        self.assertEqual(run(due + timedelta(days=4)), ["2:before", "2:due", "2:late"])
        self.assertEqual(run(due + timedelta(days=9)), ["2:before", "2:due", "2:late"])
        # Still part paid: a missed instalment only brings reminders.
        self.assertEqual(payment.status, Payment.Status.PART_PAID)
        texts = list(first.notifications.values_list("text", flat=True))
        self.assertTrue(any("₦50,000" in text and "due" in text for text in texts))


class SameInstantChargesTests(TestCase):
    """Two charges stamped at the same instant: the newer one is always chosen."""

    def test_settlement_takes_the_newest_receipt_even_with_equal_timestamps(self):
        from apps.applications.tests.factories import make_application
        from apps.payments.settlement import _charge_to_apply

        payment = Payment.objects.create(
            application=make_application(make_user("tie@example.com")),
            amount=NGN("200000"), amount_ngn=NGN("200000"), status=Payment.Status.REVIEW,
        )
        stamp = timezone.now()
        older = PaymentCharge.objects.create(
            payment=payment, kind="deposit", amount_ngn=NGN("100000"), expected_ngn=NGN("100000"),
            gateway=Payment.Gateway.TRANSFER, status="review",
        )
        newer = PaymentCharge.objects.create(
            payment=payment, kind="balance", amount_ngn=NGN("200000"), expected_ngn=NGN("200000"),
            gateway=Payment.Gateway.TRANSFER, status="review",
        )
        PaymentCharge.objects.filter(pk__in=[older.pk, newer.pk]).update(created_at=stamp)
        for _ in range(5):
            self.assertEqual(_charge_to_apply(payment, Payment.Gateway.TRANSFER, None).pk, newer.pk)
