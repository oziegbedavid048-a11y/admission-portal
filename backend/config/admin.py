"""How the admissions desk is laid out.

Django lists apps alphabetically and names them after the code, which puts
"Accounts" first and buries the screens people actually open. This orders the
index by the work: applications first, then partners, money, the catalogue, and
finally the accounts nobody touches day to day.

It also drops Django's own Groups. Permissions here come from the role on the
user record, so an empty Groups screen is a dead end that invites mistakes.
"""

from django.contrib import admin
from django.contrib.auth.models import Group

# Section order on the index, and the order of the screens inside each one.
# Anything not named here still appears, after the sections that are.
LAYOUT = [
    ("applications", ["Application", "VisaSupportApplication", "Document", "CorrectionRequest", "Letter"]),
    ("partners", ["AgentProfile", "SupervisorProfile", "Loan", "Withdrawal", "SupervisorWithdrawal"]),
    ("payments", ["Payment"]),
    ("catalog", ["Program", "Institution", "DestinationCountry", "CourseImport"]),
    ("accounts", ["SupportTicket", "User"]),
]

SECTION_ORDER = {label: index for index, (label, _) in enumerate(LAYOUT)}
MODEL_ORDER = {
    label: {name: index for index, name in enumerate(models)} for label, models in LAYOUT
}


class GabstepAdminSite(admin.AdminSite):
    """The default site, reordered.

    Swapping the class on the existing instance rather than building a new site
    keeps every `@admin.register` decorator working untouched.
    """

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)

        for app in app_list:
            order = MODEL_ORDER.get(app["app_label"], {})
            app["models"].sort(
                key=lambda model: (order.get(model["object_name"], 99), model["name"])
            )

        app_list.sort(key=lambda app: (SECTION_ORDER.get(app["app_label"], 99), app["name"]))
        return app_list


admin.site.__class__ = GabstepAdminSite

# Groups are unused: a user's role is a field on the user.
if admin.site.is_registered(Group):
    admin.site.unregister(Group)
