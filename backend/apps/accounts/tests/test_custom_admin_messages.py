from io import BytesIO

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from apps.accounts.admin import UserAdmin
from apps.accounts.emails import extract_attachments, send_custom_message_email
from apps.accounts.models import User
from apps.applications.admin import ApplicationAdmin
from apps.applications.models import Application
from apps.catalog.models import DestinationCountry, OriginCountry
from apps.partners.admin import AgentProfileAdmin
from apps.partners.models import AgentProfile


class CustomAdminMessagesTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.staff_user = User.objects.create_superuser(
            email="admin@example.com", password="password123", full_name="Admin Staff"
        )
        self.applicant = User.objects.create_user(
            email="applicant@example.com",
            full_name="Jane Applicant",
            role=User.Role.APPLICANT,
        )
        self.agent_user = User.objects.create_user(
            email="agent@example.com",
            full_name="John Agent",
            role=User.Role.AGENT,
        )
        self.agent_profile = AgentProfile.objects.create(
            user=self.agent_user,
            agency_name="Top Agency",
            bank_name="Test Bank",
            account_number="0123456789",
            account_name="Top Agency Ltd",
        )
        self.factory = RequestFactory()

    def _prepare_request(self, req):
        req.user = self.staff_user
        SessionMiddleware(lambda r: None).process_request(req)
        setattr(req, "_messages", FallbackStorage(req))
        return req

    def test_send_custom_message_email_to_applicant_with_attachment(self):
        mail.outbox = []
        pdf_content = b"%PDF-1.4 test pdf content"
        attachments = [("welcome_doc.pdf", pdf_content, "application/pdf")]

        sent = send_custom_message_email(
            user_or_email=self.applicant,
            subject="Important update on your application",
            message_body="Please review the attached document carefully.\n\nThank you.",
            attachments=attachments,
            wait=True,
        )
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "Important update on your application")
        self.assertEqual(msg.to, ["applicant@example.com"])
        self.assertIn("Hello Jane,", msg.body)
        self.assertIn("Please review the attached document", msg.body)
        # Check attachment
        self.assertEqual(len(msg.attachments), 1)
        att_name, att_bytes, att_mime = msg.attachments[0]
        self.assertEqual(att_name, "welcome_doc.pdf")
        self.assertEqual(att_bytes, pdf_content)
        self.assertEqual(att_mime, "application/pdf")

    def test_send_custom_message_email_to_agent(self):
        mail.outbox = []
        sent = send_custom_message_email(
            user_or_email=self.agent_user,
            subject="Commission structure update",
            message_body="We have updated our commission rates.",
            wait=True,
        )
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["agent@example.com"])
        self.assertIn("Hello John,", msg.body)
        self.assertNotIn("/agent/dashboard", msg.body)

    def test_extract_attachments_helper(self):
        test_file = SimpleUploadedFile("sample.txt", b"Hello world", content_type="text/plain")
        request = self.factory.post("/test", {"attachments": test_file})
        request.FILES["attachments"] = test_file

        extracted = extract_attachments(request)
        self.assertEqual(len(extracted), 1)
        name, content, mime = extracted[0]
        self.assertEqual(name, "sample.txt")
        self.assertEqual(content, b"Hello world")
        self.assertEqual(mime, "text/plain")

    def test_user_admin_action_send_custom_message(self):
        admin = UserAdmin(User, self.site)
        mail.outbox = []

        # 1. GET intermediate form
        req = self._prepare_request(self.factory.get("/admin/accounts/user/"))
        qs = User.objects.filter(pk__in=[self.applicant.pk, self.agent_user.pk])
        response = admin.action_send_custom_message(req, qs)
        self.assertEqual(response.status_code, 200)

        # 2. POST to send message
        test_pdf = SimpleUploadedFile("test.pdf", b"PDF bytes", content_type="application/pdf")
        post_req = self._prepare_request(self.factory.post(
            "/admin/accounts/user/",
            {
                "apply": "send_custom_message",
                "subject": "Broadcast notice",
                "message": "Notice for all applicants and agents.",
                "attachments": test_pdf,
            },
        ))
        post_req.FILES["attachments"] = test_pdf

        response = admin.action_send_custom_message(post_req, qs)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        recipients = {m.to[0] for m in mail.outbox}
        self.assertEqual(recipients, {"applicant@example.com", "agent@example.com"})
        for m in mail.outbox:
            self.assertEqual(len(m.attachments), 1)
            self.assertEqual(m.attachments[0][0], "test.pdf")

    def test_user_admin_send_custom_message_view(self):
        admin = UserAdmin(User, self.site)
        mail.outbox = []

        # 1. GET view
        req = self._prepare_request(self.factory.get("/admin/accounts/user/send-message/?user=" + str(self.applicant.pk)))
        response = admin.send_custom_message_view(req)
        self.assertEqual(response.status_code, 200)

        # 2. POST view
        test_file = SimpleUploadedFile("guide.pdf", b"guide data", content_type="application/pdf")
        post_req = self._prepare_request(self.factory.post(
            "/admin/accounts/user/send-message/",
            {
                "subject": "Your Visa Guide",
                "message": "Here is the visa guide document.",
                "recipients": [str(self.applicant.pk)],
                "attachments": test_file,
            },
        ))
        post_req.FILES["attachments"] = test_file

        response = admin.send_custom_message_view(post_req)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["applicant@example.com"])
        self.assertEqual(mail.outbox[0].attachments[0][0], "guide.pdf")

    def test_agent_profile_admin_action_send_custom_message(self):
        admin = AgentProfileAdmin(AgentProfile, self.site)
        mail.outbox = []

        test_file = SimpleUploadedFile("agent_policy.pdf", b"policy", content_type="application/pdf")
        post_req = self._prepare_request(self.factory.post(
            "/admin/partners/agentprofile/",
            {
                "apply": "send_custom_message",
                "subject": "Agent Policy Update",
                "message": "Updated terms of engagement.",
                "attachments": test_file,
            },
        ))
        post_req.FILES["attachments"] = test_file

        qs = AgentProfile.objects.filter(pk=self.agent_profile.pk)
        response = admin.action_send_custom_message(post_req, qs)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["agent@example.com"])
        self.assertEqual(mail.outbox[0].attachments[0][0], "agent_policy.pdf")

    def test_application_admin_action_send_email_with_attachment(self):
        from decimal import Decimal
        origin = OriginCountry.objects.create(name="Nigeria", currency="NGN", symbol="₦", ngn_per_unit=Decimal("1.0"))
        destination = DestinationCountry.objects.create(name="United Kingdom", code="GB")
        application = Application.objects.create(
            applicant=self.applicant,
            origin_country=origin,
            destination_country=destination,
            full_name="Jane Applicant",
            email="applicant@example.com",
            phone="+441234567890",
        )
        admin = ApplicationAdmin(Application, self.site)
        mail.outbox = []

        test_file = SimpleUploadedFile("offer_brief.pdf", b"offer content", content_type="application/pdf")
        post_req = self._prepare_request(self.factory.post(
            "/admin/applications/application/",
            {
                "apply": "send_email",
                "subject": "Additional application requirement",
                "message": "Please see attached brief.",
                "attachments": test_file,
            },
        ))
        post_req.FILES["attachments"] = test_file

        qs = Application.objects.filter(pk=application.pk)
        response = admin.action_send_email_to_applicants(post_req, qs)
        self.assertIsNone(response)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["applicant@example.com"])
        self.assertEqual(len(mail.outbox[0].attachments), 1)
        self.assertEqual(mail.outbox[0].attachments[0][0], "offer_brief.pdf")
