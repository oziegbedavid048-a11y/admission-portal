from rest_framework.permissions import BasePermission


class IsAgent(BasePermission):
    """Only a signed-in user who has a partner profile."""

    message = "This area is for registered partner agents."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "agent_profile", None) is not None
        )


class ContractSigned(BasePermission):
    """A new agent signs the partnership contract before using the portal.

    The portal sends them to the Contract page; this says the same thing to
    anything calling the API directly. Views an unsigned agent still needs (their
    profile, wallet, and the contract itself) set ``contract_exempt = True``.
    """

    message = "Sign your partnership contract to continue."
    code = "contract_required"

    def has_permission(self, request, view):
        if getattr(view, "contract_exempt", False):
            return True
        agent = getattr(request.user, "agent_profile", None)
        return agent is None or agent.contract_status != "pending"
