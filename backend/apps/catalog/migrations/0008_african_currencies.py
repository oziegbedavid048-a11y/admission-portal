"""Every African country an agent can sign up from, on the Exchange rates table.

Agents outside Nigeria are paid and shown their own currency, and the table is
what maps a country to its currency. Only fourteen African countries were on
it, so an agent from Benin, Malawi or Tunisia would have been shown Naira.

The rates are reference rates for when the live provider cannot be reached
(taken from the live rates when this was written: Naira per unit). Live rates
are always used first. Existing rows are left exactly as they are.
"""

from decimal import Decimal

from django.db import migrations

# name, currency, symbol, Naira per unit
AFRICA = [
    ("Algeria", "DZD", "DA", "9.932"),
    ("Angola", "AOA", "Kz", "1.4426"),
    ("Benin", "XOF", "CFA", "2.3018"),
    ("Botswana", "BWP", "P", "95.2381"),
    ("Burkina Faso", "XOF", "CFA", "2.3018"),
    ("Burundi", "BIF", "FBu", "0.4398"),
    ("Cabo Verde", "CVE", "Esc", "13.6928"),
    ("Central African Republic", "XAF", "FCFA", "2.3018"),
    ("Chad", "XAF", "FCFA", "2.3018"),
    ("Comoros", "KMF", "CF", "3.069"),
    ("Congo (Brazzaville)", "XAF", "FCFA", "2.3018"),
    ("Congo (DRC)", "CDF", "FC", "0.5766"),
    ("Djibouti", "DJF", "Fdj", "7.4892"),
    ("Equatorial Guinea", "XAF", "FCFA", "2.3018"),
    ("Eritrea", "ERN", "Nfk", "88.7311"),
    ("Eswatini", "SZL", "E", "81.5661"),
    ("Gabon", "XAF", "FCFA", "2.3018"),
    ("Gambia", "GMD", "D", "18.1812"),
    ("Guinea", "GNF", "FG", "0.154"),
    ("Guinea-Bissau", "XOF", "CFA", "2.3018"),
    ("Ivory Coast", "XOF", "CFA", "2.3018"),
    ("Lesotho", "LSL", "L", "81.5661"),
    ("Liberia", "LRD", "L$", "7.7476"),
    ("Libya", "LYD", "LD", "207.5119"),
    ("Madagascar", "MGA", "Ar", "0.2976"),
    ("Malawi", "MWK", "MK", "0.7763"),
    ("Mali", "XOF", "CFA", "2.3018"),
    ("Mauritania", "MRU", "UM", "33.0469"),
    ("Mauritius", "MUR", "Rs", "28.1571"),
    ("Mozambique", "MZN", "MT", "21.1184"),
    ("Namibia", "NAD", "N$", "81.5661"),
    ("Niger", "XOF", "CFA", "2.3018"),
    ("Sao Tome and Principe", "STN", "Db", "61.6257"),
    ("Seychelles", "SCR", "SR", "94.0557"),
    ("Sierra Leone", "SLE", "Le", "53.8648"),
    ("Somalia", "SOS", "Sh", "2.3233"),
    ("South Sudan", "SSP", "SSP", "0.2247"),
    ("Sudan", "SDG", "SDG", "2.9282"),
    ("Togo", "XOF", "CFA", "2.3018"),
    ("Tunisia", "TND", "DT", "448.2295"),
]


def add(apps, schema_editor):
    OriginCountry = apps.get_model("catalog", "OriginCountry")
    for name, currency, symbol, rate in AFRICA:
        if OriginCountry.objects.filter(name__iexact=name).exists():
            continue
        OriginCountry.objects.create(
            name=name, currency=currency, symbol=symbol, ngn_per_unit=Decimal(rate)
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_search_indexes"),
    ]

    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
