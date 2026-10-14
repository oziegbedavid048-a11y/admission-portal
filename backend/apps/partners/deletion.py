"""What goes when an agent account is deleted.

An agent owns more than their own login: the applications they filed, and the
student accounts that were created to hold those files. Deleting only the agent
used to leave all of that behind (an application's link to its agent is
cleared, not cascaded), so a deleted agent's students stayed in the admin and
the portal with nobody responsible for them.

Deleting an agent now deletes the lot: every application they filed, with its
documents, fee record, letters, notes and commissions, and each student account
that is left holding nothing once those files are gone. A student who also has
an application of their own keeps their account and that application.
"""


def agent_applications(agent):
    from apps.applications.models import Application

    return Application.objects.filter(submitted_by_agent=agent)


def removable_students(agent):
    """The students whose accounts go with the agent: applicants who have no
    application other than the ones this agent filed."""
    from apps.accounts.models import User
    from apps.applications.models import Application

    candidates = User.objects.filter(
        pk__in=agent_applications(agent).values("applicant_id"),
        role=User.Role.APPLICANT,
        is_staff=False,
        is_superuser=False,
    ).exclude(pk=agent.user_id)
    return [
        student
        for student in candidates
        if not Application.objects.filter(applicant=student).exclude(submitted_by_agent=agent).exists()
    ]


def summary(agent):
    """(applications, student accounts) that deleting this agent also removes."""
    return agent_applications(agent).count(), len(removable_students(agent))


def delete_agent_data(agent):
    """Delete everything that belongs to the agent, apart from the agent.

    Runs just before the agent row goes (see apps.py), inside the same
    transaction, so a failure leaves nothing half deleted.
    """
    students = removable_students(agent)
    # Each application takes its documents, fee record, letters, corrections,
    # notes, commissions and manager bonuses with it, and their stored files.
    for application in list(agent_applications(agent)):
        application.delete()
    for student in students:
        student.delete()


def delete_agent_account(agent):
    """Delete an agent for good: their login too, not just the partner record.

    Deleting the login takes the partner record with it, and the partner record
    takes the applications and students (see delete_agent_data). A login that
    belongs to staff, or to a sales manager as well, is kept and only the agent
    side is removed.
    """
    user = agent.user
    shared = user.is_staff or user.is_superuser or getattr(user, "supervisor_profile", None) is not None
    if user.role == user.Role.AGENT and not shared:
        user.delete()
    else:
        agent.delete()
