"""Transaction boundaries from the October 2026 audit.

* An application and the documents copied from its draft are saved together or
  not at all.
* Checkout's call to Paystack runs outside the database transaction, so a slow
  answer does not hold a connection and a transaction open.
"""

from decimal import Decimal
from unittest import mock

from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from apps.applications.models import Application, ApplicationDraft, ApplicationDraftFile
from apps.applications.tests.factories import make_application, make_user
from apps.catalog.models import DestinationCountry, Institution, OriginCountry
from apps.payments.models import Payment


class ApplicationCreateIsAtomicTests(TestCase):
    def setUp(self):
        OriginCountry.objects.create(name="Nigeria", currency="NGN", symbol="N", ngn_per_unit=Decimal("1"))
        DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        self.user = make_user("ada@example.com", full_name="Ada Lovelace")
        draft = ApplicationDraft.objects.create(user=self.user)
        ApplicationDraftFile.objects.create(
            draft=draft, slot="passport", kind="passport", name="Passport",
            file=ContentFile(b"%PDF-1.4 test", name="passport.pdf"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def submit(self):
        return self.client.post(
            "/api/applications/",
            {
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "phone": "+2348000000000",
                "origin_country": "Nigeria",
                "destination_country": "Canada",
                "previous_schools": "School",
                "qualification": "BSc",
                "year_graduated": 2020,
                "grade_gpa": "4.0",
                "is_custom_course": True,
                "custom_course_name": "Nursing",
            },
            format="json",
        )

    def test_a_failure_copying_documents_leaves_no_half_made_file(self):
        with mock.patch(
            "apps.applications.views.Document.objects.create", side_effect=OSError("storage down")
        ), self.assertLogs("apps.applications.views", level="ERROR"):
            response = self.submit()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Application.objects.filter(applicant=self.user).exists())
        # The draft and its document are still there to try again with.
        self.assertTrue(ApplicationDraftFile.objects.filter(draft__user=self.user).exists())

        retry = self.submit()
        self.assertEqual(retry.status_code, 201, retry.content)
        application = Application.objects.get(applicant=self.user)
        self.assertEqual(application.documents.count(), 1)


class CheckoutOutsideTransactionTests(TestCase):
    def test_paystack_is_called_outside_the_transaction(self):
        canada = DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        school = Institution.objects.create(
            slug="maple", name="Maple College", country=canada,
            application_fee=Decimal("5000"), application_fee_currency="NGN",
        )
        owner = make_user("owner@example.com")
        application = make_application(owner, institution=school)
        client = APIClient()
        client.force_authenticate(owner)

        outer_depth = len(connection.atomic_blocks)
        depth_at_call = []

        def initiate(payment, email, callback_url, charge=None):
            depth_at_call.append(len(connection.atomic_blocks))
            return "https://checkout.paystack.test/x"

        with mock.patch("apps.payments.views.gateway.initiate", side_effect=initiate):
            response = client.post(
                "/api/payments/checkout/", {"application": application.reference}, format="json"
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["authorization_url"], "https://checkout.paystack.test/x")
        # Only the test's own transaction is open when Paystack is called.
        self.assertEqual(depth_at_call, [outer_depth])
        self.assertEqual(Payment.objects.get(application=application).status, Payment.Status.PENDING)
