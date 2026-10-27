"""Nigeria's support WhatsApp number is now +234 915 555 6655 (David, 27 October 2026).

Only the Nigeria entry changes; numbers for other countries are left as they
are. The number can still be edited any time under WhatsApp numbers in the
admin.
"""

from django.db import migrations

NEW_NUMBER = "+234 915 555 6655"


def update_number(apps, schema_editor):
    WhatsAppContact = apps.get_model("accounts", "WhatsAppContact")
    contact = WhatsAppContact.objects.filter(country__iexact="Nigeria").first()
    if contact is None:
        WhatsAppContact.objects.create(country="Nigeria", phone=NEW_NUMBER, display_order=1)
        return
    contact.phone = NEW_NUMBER
    contact.is_active = True
    contact.save(update_fields=["phone", "is_active"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_whatsapp_contacts"),
    ]

    operations = [
        migrations.RunPython(update_number, migrations.RunPython.noop),
    ]
