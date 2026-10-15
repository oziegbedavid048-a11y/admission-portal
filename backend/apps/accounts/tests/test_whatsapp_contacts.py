"""Support WhatsApp numbers: one icon per active country, edited in the admin."""

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, WhatsAppContact

URL = "/api/auth/support/whatsapp/"


class WhatsAppContactsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(email="a@example.com", password="x-123456789"))

    def test_nigeria_is_there_from_the_start(self):
        self.assertEqual(
            self.client.get(URL).json(),
            [{"country": "Nigeria", "phone": "+234 805 900 0074", "link": "https://wa.me/2348059000074"}],
        )

    def test_a_number_added_in_the_admin_shows_and_an_inactive_one_does_not(self):
        WhatsAppContact.objects.create(country="Ghana", phone="+233 20 000 0000", display_order=2)
        WhatsAppContact.objects.create(country="Gambia", phone="+220 300 0000", display_order=3, is_active=False)
        self.assertEqual([row["country"] for row in self.client.get(URL).json()], ["Nigeria", "Ghana"])

    def test_signed_in_only(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    def test_a_number_without_a_country_code_is_refused(self):
        with self.assertRaises(ValidationError):
            WhatsAppContact(country="Ghana", phone="0200").full_clean()
