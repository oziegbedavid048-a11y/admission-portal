"""Applicants see a school code, not the school's name, until they pay.

Applicants were browsing the catalogue, noting the school and applying
elsewhere. So everything sent to an applicant (or to a visitor who is not
signed in) names a school by its code, "CA-418", and leaves out what would give
it away: the campus city, the photo, the tagline, and the name wherever it
appears in a course's text. Countries, courses, levels, tuition and fees stay.

The name shows once the applicant has paid the application fee (in full, the
first part of a plan, or waived), because by then they are committed and need
it for their documents. Agents, sales managers and staff always see names, and
so does a student whose agent filed the application.

This is done on the server, in what the API sends, so the name is never in the
data an applicant's browser receives.
"""

import re

NAMED_ROLES = ("agent", "supervisor", "staff")

# Fields of a school that would identify it, emptied for applicants.
HIDDEN_FIELDS = {"location": "", "cover_image": None, "tagline": ""}


def sees_school_names(user):
    """Whether this person may see real school names everywhere."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_staff or getattr(user, "role", "") in NAMED_ROLES)


def hides_names(request):
    return not sees_school_names(getattr(request, "user", None))


def application_reveals_school(application):
    """Whether the applicant on this file may see the school's real name."""
    if application is None:
        return False
    if getattr(application, "submitted_by_agent_id", None):
        return True
    if getattr(application, "payment_verified", False):
        return True
    payment = getattr(application, "fee_payment", None)
    return getattr(payment, "status", "") in ("paid", "waived", "part_paid")


def school_label(institution, revealed):
    """The name to show for a school: its name, or its code."""
    if institution is None:
        return ""
    return institution.name if revealed else (institution.code or "Partner school")


def _scrub_text(text, institution):
    if not text or not institution.name:
        return text
    return re.sub(re.escape(institution.name), institution.code or "the school", text, flags=re.IGNORECASE)


def _scrub(value, institution):
    """Replace the school's name wherever it appears in a block of data."""
    if isinstance(value, str):
        return _scrub_text(value, institution)
    if isinstance(value, list):
        return [_scrub(item, institution) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item, institution) for key, item in value.items()}
    return value


def mask_school(data, institution):
    """A serialized school as an applicant may see it."""
    if not data or institution is None:
        return data
    data = _scrub(dict(data), institution)
    data["name"] = institution.code
    if "slug" in data:
        data["slug"] = institution.code
    for field, empty in HIDDEN_FIELDS.items():
        if field in data:
            data[field] = empty
    return data


def mask_program_row(data, institution):
    """A course row from the catalogue, as an applicant may see it."""
    if not data or institution is None:
        return data
    data = _scrub(dict(data), institution)
    if "institution" in data:
        data["institution"] = institution.code
    if "institution_slug" in data:
        data["institution_slug"] = institution.code
    if "location" in data:
        data["location"] = ""
    return data


def find_school(value, *, by_code_only=False):
    """The active school a slug or code points at. Applicants only use codes."""
    from django.db.models import Q

    from .models import Institution

    value = str(value or "").strip()
    if not value:
        return None
    match = Q(code__iexact=value) if by_code_only else Q(code__iexact=value) | Q(slug=value)
    return Institution.objects.filter(match, is_active=True).select_related("country").first()
