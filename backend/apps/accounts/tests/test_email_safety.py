"""Gabstep's email cannot be aimed at strangers or carry injected links."""

from unittest import mock

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts import emails
from apps.applications.models import Application
from apps.applications.tests.factories import make_application, make_user

EVIL = '<a href="https://evil.example">Confirm your account</a>'


class RenderEscapingTests(TestCase):
    def test_greeting_facts_items_and_action_are_escaped(self):
        html = emails._render(
            f"Hello {EVIL},",
            ["A fixed sentence with <strong>deliberate</strong> markup."],
            facts=[("Course requested", EVIL)],
            items=[(EVIL, EVIL)],
            items_intro=EVIL,
            action=("Open", "https://apply.example.com/portal"),
        )
        self.assertNotIn('<a href="https://evil.example">', html)
        self.assertIn("&lt;a href=&quot;https://evil.example&quot;&gt;", html)
        # Deliberate markup in paragraphs is kept.
        self.assertIn("<strong>deliberate</strong>", html)

    def test_plain_text_part_is_readable(self):
        text = emails._plain("Hello Ada,", ["Tom &amp; Jerry <strong>won</strong>"])
        self.assertIn("Tom & Jerry won", text)

    def test_letter_email_escapes_the_students_name(self):
        from apps.applications.models import Letter

        from apps.accounts.models import User
        from apps.partners.models import AgentProfile

        agent_user = make_user("agent@example.com", role=User.Role.AGENT, full_name="Kemi Agent")
        agent = AgentProfile.objects.create(user=agent_user)
        student = make_user("ada@example.com", full_name=f"Ada {EVIL}")
        # The agent's copy names the student in full, so it carries the name.
        application = make_application(student, submitted_by_agent=agent)
        letter = Letter.objects.create(application=application, kind="offer", title="Offer letter", is_published=True)
        with mock.patch.object(emails, "send_async_email") as send:
            emails.send_letter_issued_email(letter)
        html_body = send.call_args.args[2]
        self.assertIn("Ada &lt;a href", html_body)
        self.assertNotIn('<a href="https://evil.example">', html_body)


class ApplicationRecipientTests(TestCase):
    def test_an_applicants_file_is_mailed_to_their_own_account(self):
        from apps.catalog.models import DestinationCountry, OriginCountry
        from decimal import Decimal

        OriginCountry.objects.create(name="Nigeria", currency="NGN", symbol="N", ngn_per_unit=Decimal("1"))
        DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        user = make_user("ada@example.com", full_name="Ada Lovelace")
        client = APIClient()
        client.force_authenticate(user)
        mail.outbox.clear()
        response = client.post(
            "/api/applications/",
            {
                "full_name": "Ada Lovelace",
                "email": "victim@example.org",
                "phone": "+2348000000000",
                "origin_country": "Nigeria",
                "destination_country": "Canada",
                "previous_schools": "School",
                "qualification": "BSc",
                "year_graduated": 2020,
                "grade_gpa": "4.0",
                "is_custom_course": True,
                "custom_course_name": EVIL,
            },
            format="json",
        )
        self.assertIn(response.status_code, (200, 201), response.content)
        self.assertEqual(Application.objects.get().email, "ada@example.com")
        recipients = {address for message in mail.outbox for address in message.to}
        self.assertNotIn("victim@example.org", recipients)
        for message in mail.outbox:
            for body, _ in message.alternatives:
                self.assertNotIn('<a href="https://evil.example">', body)
