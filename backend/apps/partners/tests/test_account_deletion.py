"""Deleting an agent or an applicant in the admin removes everything under them."""

from decimal import Decimal

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import SupportTicket, User
from apps.applications.models import Application, Document, Letter, Notification
from apps.applications.tests.factories import make_application, make_user
from apps.filestore.models import StoredFile
from apps.partners.models import (
    AgentContract,
    AgentProfile,
    Commission,
    Loan,
    StudentDraft,
    Wallet,
    Withdrawal,
)
from apps.payments.models import Payment


class DeletionBase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        self.client.force_login(self.staff)

    def post_delete(self, url_name, pk):
        url = reverse(f"admin:{url_name}_delete", args=[pk])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("Cannot delete", page.content.decode())
        return self.client.post(url, {"post": "yes"})

    def paid_application(self, applicant, agent=None, reference_suffix="1"):
        application = make_application(applicant, submitted_by_agent=agent)
        Payment.objects.create(
            application=application,
            reference=f"PAY-{reference_suffix}-{application.pk}",
            status=Payment.Status.PAID,
            amount=Decimal("200000"),
            amount_ngn=Decimal("200000"),
        )
        Document.objects.create(
            application=application,
            kind=Document.Kind.PASSPORT,
            name="Passport",
            file=ContentFile(b"%PDF-1.4 passport", name=f"passport-{application.pk}.pdf"),
        )
        Letter.objects.create(
            application=application,
            title="Admission",
            file=ContentFile(b"%PDF-1.4 letter", name=f"letter-{application.pk}.pdf"),
        )
        Notification.objects.create(application=application, text="Hello")
        return application


class DeleteAgentTests(DeletionBase):
    def setUp(self):
        super().setUp()
        self.agent_user = make_user("agent@example.com", role=User.Role.AGENT, full_name="Ada Agent")
        self.agent = AgentProfile.objects.create(user=self.agent_user, address="1 Road")
        self.wallet = Wallet.objects.create(agent=self.agent)

        # Two students the agent registered: accounts with no password.
        self.students = []
        self.applications = []
        for index in range(2):
            student = User.objects.create_user(
                email=f"student{index}@example.com", password=None, full_name=f"Student {index}",
                role=User.Role.APPLICANT,
            )
            application = self.paid_application(student, self.agent, str(index))
            Commission.objects.create(
                agent=self.agent, application=application, kind=Commission.Kind.REGISTRATION,
                amount=Decimal("30000"), amount_ngn=Decimal("30000"),
            )
            self.students.append(student)
            self.applications.append(application)

        # Money records the admin refuses to delete one at a time.
        Loan.objects.create(
            agent=self.agent, requested_amount=Decimal("80000"), approved_amount=Decimal("80000"),
            purpose="Facebook", status=Loan.Status.REPAID,
        )
        Withdrawal.objects.create(
            agent=self.agent, amount_requested=Decimal("5000"), net_amount=Decimal("5000"),
            status=Withdrawal.Status.PAID,
        )
        StudentDraft.objects.create(agent=self.agent, data={"fullName": "Draft"})
        AgentContract.objects.create(
            agent=self.agent, file=ContentFile(b"%PDF-1.4 contract", name="contract.pdf")
        )
        SupportTicket.objects.create(user=self.agent_user, subject="Help", message="Hi")

    def assert_everything_gone(self):
        self.assertFalse(User.objects.filter(email="agent@example.com").exists())
        self.assertFalse(AgentProfile.objects.exists())
        self.assertFalse(Wallet.objects.exists())
        self.assertFalse(Application.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Letter.objects.exists())
        self.assertFalse(Commission.objects.exists())
        self.assertFalse(Loan.objects.exists())
        self.assertFalse(Withdrawal.objects.exists())
        self.assertFalse(StudentDraft.objects.exists())
        self.assertFalse(AgentContract.objects.exists())
        self.assertFalse(SupportTicket.objects.exists())
        self.assertFalse(User.objects.filter(email__startswith="student").exists())
        self.assertEqual(StoredFile.objects.count(), 0)
        # Only the staff account is left.
        self.assertEqual(list(User.objects.values_list("email", flat=True)), ["desk@example.com"])

    def test_deleting_the_agent_profile_removes_everything_under_it(self):
        response = self.post_delete("partners_agentprofile", self.agent.pk)
        self.assertEqual(response.status_code, 302)
        self.assert_everything_gone()

    def test_deleting_the_agent_user_removes_everything_under_it(self):
        response = self.post_delete("accounts_user", self.agent_user.pk)
        self.assertEqual(response.status_code, 302)
        self.assert_everything_gone()

    def test_bulk_delete_from_the_agents_list(self):
        response = self.client.post(
            reverse("admin:partners_agentprofile_changelist"),
            {"action": "delete_selected", "_selected_action": [self.agent.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 302)
        self.assert_everything_gone()

    def test_a_student_with_an_application_of_their_own_keeps_their_account(self):
        own = make_user("own@example.com", full_name="Has Own Application")
        make_application(own)
        make_application(own, submitted_by_agent=self.agent, full_name="Filed by agent")
        self.post_delete("partners_agentprofile", self.agent.pk)
        self.assertTrue(User.objects.filter(email="own@example.com").exists())
        self.assertEqual(own.applications.count(), 1)
        self.assertIsNone(own.applications.get().submitted_by_agent)

    def test_other_agents_are_untouched(self):
        other_user = make_user("other@example.com", role=User.Role.AGENT)
        other = AgentProfile.objects.create(user=other_user)
        Wallet.objects.create(agent=other)
        student = make_user("kept@example.com")
        kept = self.paid_application(student, other, "k")
        self.post_delete("partners_agentprofile", self.agent.pk)
        self.assertTrue(AgentProfile.objects.filter(pk=other.pk).exists())
        self.assertTrue(Application.objects.filter(pk=kept.pk).exists())
        self.assertTrue(Payment.objects.filter(application=kept).exists())

    def test_the_confirmation_page_says_what_else_goes(self):
        page = self.client.get(
            reverse("admin:partners_agentprofile_delete", args=[self.agent.pk])
        ).content.decode()
        self.assertIn("2 applications", page)


class DeleteApplicantTests(DeletionBase):
    def setUp(self):
        super().setUp()
        self.applicant = make_user("applicant@example.com", full_name="Real Applicant")
        self.application = self.paid_application(self.applicant)

    def test_deleting_an_applicant_removes_their_whole_file(self):
        response = self.post_delete("applications_applicant", self.applicant.pk)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email="applicant@example.com").exists())
        self.assertFalse(Application.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Letter.objects.exists())
        self.assertEqual(StoredFile.objects.count(), 0)

    def test_deleting_from_the_users_screen_works_too(self):
        response = self.post_delete("accounts_user", self.applicant.pk)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Application.objects.exists())

    def test_bulk_delete_from_the_applicants_list(self):
        response = self.client.post(
            reverse("admin:applications_applicant_changelist"),
            {"action": "delete_selected", "_selected_action": [self.applicant.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email="applicant@example.com").exists())
        self.assertFalse(Payment.objects.exists())

    def test_an_agent_filed_student_can_be_deleted_and_the_agent_stays(self):
        agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        agent = AgentProfile.objects.create(user=agent_user)
        Wallet.objects.create(agent=agent)
        student = User.objects.create_user(email="s@example.com", password=None, role=User.Role.APPLICANT)
        self.paid_application(student, agent, "s")
        self.post_delete("applications_applicant", student.pk)
        self.assertFalse(User.objects.filter(email="s@example.com").exists())
        self.assertTrue(AgentProfile.objects.filter(pk=agent.pk).exists())


class DeleteTestAgentTests(DeletionBase):
    def test_a_test_agent_is_deleted_from_the_test_accounts_screen(self):
        from apps.applications.models import Application as App

        agent_user = make_user("test.agent@example.com", role=User.Role.AGENT, is_test_account=True)
        agent = AgentProfile.objects.create(user=agent_user)
        Wallet.objects.create(agent=agent)
        student = User.objects.create_user(
            email="test.student@example.com", password=None, role=User.Role.APPLICANT, is_test_account=True
        )
        self.paid_application(student, agent, "t")
        response = self.client.post(
            reverse("admin:testaccounts_testagent_changelist"),
            {"action": "delete_selected", "_selected_action": [agent.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AgentProfile.objects.exists())
        self.assertFalse(App.objects.exists())
        self.assertEqual(list(User.objects.values_list("email", flat=True)), ["desk@example.com"])
