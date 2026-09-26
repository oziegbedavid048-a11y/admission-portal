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
