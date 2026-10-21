"""Saving a profile never writes back an old copy of the money columns.

The profile is read when the request begins. Saving every column used to write
that copy back, so a payout requested in another tab while the profile form
was being saved was undone, and the same balance could be withdrawn twice.
"""

from decimal import Decimal

from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.applications.tests.factories import make_user
from apps.partners.models import AgentProfile, SupervisorProfile, Wallet
from apps.partners.serializers import AgentProfileSerializer
from apps.partners.supervisor_serializers import SupervisorProfileSerializer


def _request(user):
    request = RequestFactory().patch("/")
    request.user = user
    return request


class StaleProfileSaveTests(TestCase):
    def test_manager_profile_edit_keeps_a_payout_made_meanwhile(self):
        user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        SupervisorProfile.objects.create(user=user, bonus_total=Decimal("200000"))
        stale = SupervisorProfile.objects.select_related("user").get(user=user)

        # A payout and a new bonus land while the profile form is being saved.
        SupervisorProfile.objects.filter(pk=stale.pk).update(
            total_withdrawn=Decimal("150000"), bonus_total=Decimal("202000")
        )

        serializer = SupervisorProfileSerializer(
            stale, data={"region": "Lagos", "full_name": "Ngozi Manager"}, partial=True,
            context={"request": _request(user)},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        fresh = SupervisorProfile.objects.get(pk=stale.pk)
        self.assertEqual(fresh.region, "Lagos")
        self.assertEqual(fresh.user.full_name, "Ngozi Manager")
        self.assertEqual(fresh.total_withdrawn, Decimal("150000"))
        self.assertEqual(fresh.bonus_total, Decimal("202000"))
        # So only the 52,000 left can still be asked for.
        self.assertEqual(fresh.available_balance, Decimal("52000"))

    def test_agent_profile_edit_keeps_a_contract_signed_meanwhile(self):
        user = make_user("agent@example.com", role=User.Role.AGENT)
        AgentProfile.objects.create(user=user, contract_required=True)
        stale = AgentProfile.objects.select_related("user").get(user=user)
        Wallet.objects.create(agent=stale)

        AgentProfile.objects.filter(pk=stale.pk).update(contract_required=False)

        serializer = AgentProfileSerializer(
            stale, data={"agency_name": "Bright Paths"}, partial=True, context={"request": _request(user)}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        fresh = AgentProfile.objects.get(pk=stale.pk)
        self.assertEqual(fresh.agency_name, "Bright Paths")
        self.assertFalse(fresh.contract_required)

    def test_bank_change_still_resets_verification(self):
        user = make_user("agent2@example.com", role=User.Role.AGENT)
        from django.utils import timezone

        profile = AgentProfile.objects.create(
            user=user, bank_name="Old Bank", account_number="0123456789", account_name="Ada",
            account_verified_at=timezone.now(), paystack_recipient_code="RCP_old",
        )
        Wallet.objects.create(agent=profile)
        serializer = AgentProfileSerializer(
            profile,
            data={"bank_name": "New Bank", "account_number": "9876543210", "current_password": "Strong-pass-123"},
            partial=True,
            context={"request": _request(user)},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        fresh = AgentProfile.objects.get(pk=profile.pk)
        self.assertEqual(fresh.account_number, "9876543210")
        self.assertIsNone(fresh.account_verified_at)
        self.assertEqual(fresh.paystack_recipient_code, "")
        self.assertIsNotNone(fresh.payout_account_changed_at)
