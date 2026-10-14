"""The partnership contract: signed in the portal before anything else."""

import base64
import io
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from PIL import Image, ImageDraw
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.partners.contract_pdf import contract_terms, number_in_words
from apps.partners.models import AgentContract, AgentProfile, Wallet


def signature_data_url(blank=False):
    image = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    if not blank:
        ImageDraw.Draw(image).line([(10, 100), (120, 20), (260, 90), (390, 30)], fill=(30, 58, 138, 255), width=5)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


class ContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ada@example.com", full_name="Ada Kwame", phone="+2348011112222",
            role=User.Role.AGENT, country="Nigeria",
        )
        self.agent = AgentProfile.objects.create(
            user=self.user, address="12 Allen Avenue, Ikeja", contract_required=True
        )
        Wallet.objects.create(agent=self.agent, currency="NGN")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def refresh_client(self):
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))

    def sign(self, **overrides):
        payload = {"signature": signature_data_url(), "method": "drawn", "agree": True, **overrides}
        return self.client.post("/api/partners/contract/sign/", payload, format="json")

    def test_a_new_agent_is_held_on_the_contract(self):
        self.assertEqual(self.client.get("/api/partners/me/").json()["contract_status"], "pending")
        self.assertEqual(self.client.get("/api/partners/students/").status_code, 403)
        self.assertEqual(self.client.get("/api/partners/wallet/").status_code, 200)
        details = self.client.get("/api/partners/contract/").json()["details"]
        self.assertEqual(details["name"], "Ada Kwame")
        self.assertEqual(details["address"], "12 Allen Avenue, Ikeja")

    def test_preview_is_the_contract_pdf(self):
        response = self.client.get("/api/partners/contract/preview/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_signing_stores_the_pdf_emails_a_copy_and_opens_the_portal(self):
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            response = self.sign()
        self.assertEqual(response.status_code, 201, response.content)

        contract = AgentContract.objects.get(agent=self.agent)
        self.assertEqual(contract.source, AgentContract.Source.PORTAL)
        self.assertEqual(contract.signer_name, "Ada Kwame")
        self.assertTrue(contract.file.name)
        self.assertIsNotNone(contract.emailed_at)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ada@example.com"])
        name, content, mimetype = mail.outbox[0].attachments[0]
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))

        self.refresh_client()
        self.assertEqual(self.client.get("/api/partners/students/").status_code, 200)
        file_response = self.client.get("/api/partners/contract/file/")
        self.assertEqual(file_response.status_code, 200)
        self.assertTrue(file_response.content.startswith(b"%PDF"))

    def test_a_blank_signature_or_no_agreement_is_refused(self):
        self.assertEqual(self.sign(signature=signature_data_url(blank=True)).status_code, 400)
        self.assertEqual(self.sign(agree=False).status_code, 400)
        self.assertEqual(self.sign(signature="data:text/html;base64,PGgxPg==").status_code, 400)
        self.assertFalse(AgentContract.objects.exists())

    def test_it_cannot_be_signed_twice(self):
        self.assertEqual(self.sign().status_code, 201)
        self.refresh_client()
        self.assertEqual(self.sign().status_code, 400)

    def test_an_address_is_needed(self):
        self.agent.address = ""
        self.agent.save()
        self.refresh_client()
        self.assertEqual(self.sign().status_code, 400)
        self.assertEqual(self.sign(address="4 Marina Road, Lagos").status_code, 201)
        self.assertEqual(AgentContract.objects.get().signer_address, "4 Marina Road, Lagos")

    def test_existing_agents_are_not_asked(self):
        self.agent.contract_required = False
        self.agent.save()
        self.refresh_client()
        self.assertEqual(self.client.get("/api/partners/me/").json()["contract_status"], "none")
        self.assertEqual(self.client.get("/api/partners/students/").status_code, 200)

    def test_a_staff_upload_counts_as_signed(self):
        from django.core.files.base import ContentFile

        self.agent.contract_required = False
        self.agent.save()
        AgentContract.objects.create(agent=self.agent, file=ContentFile(b"%PDF-1.4 paper", name="paper.pdf"))
        self.refresh_client()
        self.assertEqual(self.client.get("/api/partners/contract/").json()["status"], "signed")
        self.assertEqual(self.client.get("/api/partners/contract/file/").status_code, 200)


class SignUpTests(TestCase):
    def test_sign_up_takes_an_address_and_asks_for_the_contract(self):
        from apps.accounts.serializers import AgentRegistrationSerializer

        data = {
            "email": "new.agent@example.com", "full_name": "New Agent", "phone": "+2348000000001",
            "country": "Nigeria", "password": "Strong-pass-123", "bank_name": "GTB",
            "account_number": "0123456789", "account_name": "New Agent",
        }
        self.assertFalse(AgentRegistrationSerializer(data=data).is_valid())
        serializer = AgentRegistrationSerializer(data={**data, "address": "3 Broad Street, Lagos"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        profile = serializer.save().agent_profile
        self.assertEqual(profile.address, "3 Broad Street, Lagos")
        self.assertTrue(profile.contract_required)
        self.assertEqual(profile.contract_status, "pending")


class ContractWordingTests(TestCase):
    def test_numbers_in_words(self):
        self.assertEqual(number_in_words(30000), "Thirty Thousand")
        self.assertEqual(number_in_words(1500), "One Thousand Five Hundred")
        self.assertEqual(number_in_words(450000), "Four Hundred Fifty Thousand")

    def test_local_estimates_add_up(self):
        terms = contract_terms(30000, 50000, "GMD", Decimal("18.1812"))
        amounts = terms["local"]["amounts"]
        self.assertEqual(amounts[30000], 1650)
        self.assertEqual(amounts[80000], amounts[30000] + amounts[50000])
        self.assertEqual(amounts[480000], amounts[80000] * 6)

    def test_nigeria_has_no_estimates(self):
        self.assertNotIn("local", contract_terms(30000, 50000, "NGN", None))


class ContractAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        user = User.objects.create_user(email="agent@example.com", full_name="Ada Agent", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=user)
        Wallet.objects.create(agent=self.agent)
        self.client.force_login(self.staff)

    def test_signed_contract_downloads_beside_the_certificate(self):
        from django.core.files.base import ContentFile
        from django.urls import reverse

        page = self.client.get(reverse("admin:partners_agentprofile_change", args=[self.agent.pk])).content.decode()
        self.assertIn("Contract", page)
        AgentContract.objects.create(agent=self.agent, file=ContentFile(b"%PDF-1.4 signed", name="signed.pdf"))
        page = self.client.get(reverse("admin:partners_agentprofile_changelist")).content.decode()
        url = reverse("admin:agent-contract-download", args=[self.agent.pk])
        self.assertIn(url, page)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_staff_upload_a_paper_contract(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.partners.admin import AgentContractForm

        form = AgentContractForm(
            data={"signed_on": "2026-10-06"},
            files={"file": SimpleUploadedFile("paper.pdf", b"%PDF-1.4 paper contract", content_type="application/pdf")},
            instance=AgentContract(agent=self.agent),
        )
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(contract.source, AgentContract.Source.UPLOADED)
        self.assertEqual(self.agent.__class__.objects.get(pk=self.agent.pk).contract_status, "signed")

    def test_a_disguised_upload_is_refused(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.partners.admin import AgentContractForm

        form = AgentContractForm(
            data={"signed_on": "2026-10-06"},
            files={"file": SimpleUploadedFile("paper.pdf", b"<html>not a pdf</html>", content_type="application/pdf")},
            instance=AgentContract(agent=self.agent),
        )
        self.assertFalse(form.is_valid())


class SignatureQualityTests(TestCase):
    def test_a_dot_is_not_a_signature(self):
        from apps.partners.contract import ContractError, decode_signature

        image = Image.new("RGBA", (1200, 300), (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse([600, 150, 612, 162], fill=(30, 58, 138, 255))
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        with self.assertRaises(ContractError):
            decode_signature("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode())
