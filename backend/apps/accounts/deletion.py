"""Admin screens that delete a whole account.

Some records refuse to be deleted one at a time: a paid fee, a paid-out
withdrawal, repaid ads funding. Those protections stop someone removing a single
line of the books and leaving the rest inconsistent, and they are right for that.

Deleting an agent or an applicant is a different act: the account and everything
under it go together, so nothing is left pointing at a record that no longer
exists. Django's delete page checks every record that would go and refuses the
whole delete if the admin would not delete one of them on its own, which meant an
account with a single paid fee could never be removed. These screens answer for
the account as a whole instead, and say plainly what else will go.
"""


def _plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class AccountDeleteMixin:
    """Admin mixin for the screens that delete an agent or an applicant."""

    def get_deleted_objects(self, objs, request):
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        # Only the account itself needs the permission.
        perms_needed = {name for name in perms_needed if name == self.model._meta.verbose_name}
        note = self._agent_note(objs)
        if note:
            to_delete = [note, *to_delete]
        return to_delete, model_count, perms_needed, protected

    def delete_model(self, request, obj):
        from apps.partners.deletion import delete_agent_account
        from apps.partners.models import AgentProfile

        if isinstance(obj, AgentProfile):
            delete_agent_account(obj)
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        from apps.partners.deletion import delete_agent_account
        from apps.partners.models import AgentProfile

        if issubclass(queryset.model, AgentProfile):
            for agent in list(queryset):
                delete_agent_account(agent)
        else:
            super().delete_queryset(request, queryset)

    def _agent_note(self, objs):
        from apps.partners.deletion import summary
        from apps.partners.models import AgentProfile

        applications = students = 0
        for obj in objs:
            agent = obj if isinstance(obj, AgentProfile) else getattr(obj, "agent_profile", None)
            if agent is None:
                continue
            found_applications, found_students = summary(agent)
            applications += found_applications
            students += found_students
        if not applications:
            return "The agent's sign-in account is deleted too." if any(isinstance(o, AgentProfile) for o in objs) else ""
        note = (
            f"Also deleted with the agent: {_plural(applications, 'application')} they filed, "
            "with their documents, fee records, letters and commissions"
        )
        if students:
            note += f", and {_plural(students, 'student account')}"
        note += "."
        if any(isinstance(obj, AgentProfile) for obj in objs):
            note += " The agent's sign-in account is deleted too."
        return note
