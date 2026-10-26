"""Five French schools supplied by the desk on 26 October 2026.

ECE Engineering School, ESCE, INSEEC, HEIP and Sup de Pub. Every course asks
the same 3,500 EUR tuition deposit. Tuition is per year as supplied. The
language of teaching is kept in each course's note.

Used by the seed (catalogue_data.SCHOOLS) and by the migration that adds them
to the live catalogue (catalog/migrations/0012_omnes_schools.py).

Cleaned from the supplied list:
  * ECE's "MSc CGE in Cloud Computing" and INSEEC's "Bachelor in Wines and
    Spirits" were each listed twice with identical details; kept once.
  * "MSc's" / "MSC's degree" written as "MSc"; "Copywritting" as
    "Copywriting"; "Franch Only" as "French only"; a stray "Design" heading
    above Sup de Pub's "Bachelor in Motion Design" dropped.
"""

NGN_FEE = {"fee": 200000, "fee_currency": "NGN"}
DEPOSIT = {"deposit_amount": 3500}


def _lang(text):
    return f"Taught in {text}"


ECE = {
    "name": "ECE Engineering School",
    "slug": "ece-engineering-school",
    "country": "France",
    "location": "Paris, France",
    "tagline": "Engineering degrees in artificial intelligence, data, cloud and cybersecurity",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    **DEPOSIT,
    "tuition_summary": "€8,150 - €12,990 / year",
    "courses": [
        ("Bachelor in Artificial Intelligence", "bachelors", "3 years", 8850, "", _lang("French / English")),
        ("Bachelor in Data and AI Development", "bachelors", "3 years", 8150, "", _lang("French")),
        ("Bachelor in Secured Infrastructure Management", "bachelors", "3 years", 8150, "", _lang("French only")),
        ("Bachelor Application Developer", "bachelors", "3 years", 8150, "", _lang("French only")),
        ("MSc CGE AI for Digital Transformation", "masters", "1 year", 12905, "", _lang("English only")),
        ("MSc CGE Artificial Intelligence", "masters", "2 years", 12990, "", _lang("French / English")),
        ("MSc CGE Data Management", "masters", "2 years", 12290, "", _lang("French / English")),
        ("MSc CGE in Cloud Computing", "masters", "2 years", 12290, "", _lang("English only")),
        ("MSc CGE Cybersecurity Management", "masters", "2 years", 12290, "", _lang("French / English")),
        ("MSc CGE Sustainable Energy Future", "masters", "2 years", 12290, "", _lang("English only")),
        ("MSc CGE Tech Management & Innovation", "masters", "2 years", 12290, "", _lang("English only")),
    ],
}

ESCE = {
    "name": "ESCE (École Supérieure du Commerce Extérieur)",
    "slug": "esce",
    "country": "France",
    "location": "Paris, France",
    "tagline": "International business and management school",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    **DEPOSIT,
    "tuition_summary": "€8,990 - €12,190 / year",
    "courses": [
        ("Bachelor in International Business", "bachelors", "3 years", 8990, "", _lang("French, or French & English")),
        ("Master in Management", "masters", "2 years (MSc) or 5 years (BSc & MSc)", 12190, "", _lang("English, French, or French & English")),
        ("Master of Science", "masters", "2 years (MSc) or 5 years (BSc & MSc)", 12190, "", _lang("English")),
    ],
}

INSEEC = {
    "name": "INSEEC (Institut des Hautes Études Économiques et Commerciales)",
    "slug": "inseec",
    "country": "France",
    "location": "Paris, France",
    "tagline": "Business, finance, marketing, luxury and wine degrees",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    **DEPOSIT,
    "tuition_summary": "€9,350 - €11,850 / year",
    "courses": [
        ("Bachelor Business Development", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor in Wines and Spirits", "bachelors", "3 years", 9350, "", _lang("English, French")),
        ("Bachelor's Degree in Business Unit Management", "bachelors", "3 years", 9990, "", _lang("French")),
        ("Bachelor International Business", "bachelors", "3 years", 9350, "", _lang("English, or French & English")),
        ("Bachelor Luxury", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor Marketing & Product Development", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor in Marketing, Communication & Events", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor Bank Insurance", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor Corporate Finance", "bachelors", "3 years", 9350, "", _lang("English, or French & English")),
        ("Bachelor Sport Business", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor Digital Marketing", "bachelors", "3 years", 9350, "", _lang("French")),
        ("Bachelor HR – Human Resources Manager", "bachelors", "3 years", 9350, "", _lang("French")),
        ("BBA – Entrepreneurship & Innovation Major", "bachelors", "4 years", 11850, "", _lang("English, French")),
        ("BBA – International Business Management Major", "bachelors", "4 years", 11850, "", _lang("English")),
        ("BBA – International Finance Major", "bachelors", "4 years", 11850, "", _lang("English, French")),
        ("BBA – International Marketing & Data Management Major", "bachelors", "4 years", 11850, "", _lang("English, French")),
    ],
}

HEIP = {
    "name": "HEIP (Hautes Études Internationales et Politiques)",
    "slug": "heip",
    "country": "France",
    "location": "Paris, France",
    "tagline": "International relations, political science and public policy",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    **DEPOSIT,
    "tuition_summary": "€8,990 - €10,950 / year",
    "courses": [
        ("Bachelor in International Relations and Cooperation", "bachelors", "3 years", 8990, "", _lang("English")),
        ("Bachelor in Political, Institutional, and Lobbying Communication", "bachelors", "3 years", 8990, "", _lang("French")),
        ("Bachelor in International Relations & Political Science", "bachelors", "3 years", 8990, "", _lang("French")),
        ("Bachelor in Public Policy, CSR and Transitions", "bachelors", "3 years", 8990, "", _lang("French")),
        ("Bachelor in Public Management & Governance", "bachelors", "3 years", 8990, "", _lang("French")),
        ("Bachelor in Geopolitics, Security, and Defense", "bachelors", "3 years", 8990, "", _lang("French")),
        ("MSc in International Relations & Cooperation", "masters", "2 years", 10950, "", _lang("English")),
        ("MSc Expert en Relations Internationales & Coopérations", "masters", "2 years", 10950, "", _lang("English, French")),
        ("MSc in Political, Institutional Communication and Lobbying", "masters", "2 years", 10950, "", _lang("French")),
        ("MSc Public Affairs & Institutional Management", "masters", "2 years", 10950, "", _lang("French")),
        ("MSc Public Policy, CSR & Transitions", "masters", "2 years", 10950, "", _lang("French")),
        ("MSc Public Management & Governance", "masters", "2 years", 10950, "", _lang("French")),
        ("MSc Geopolitics, Security & Defense", "masters", "2 years", 10950, "", _lang("French")),
    ],
}

SUP_DE_PUB = {
    "name": "Sup de Pub – School of Communication",
    "slug": "sup-de-pub",
    "country": "France",
    "location": "Paris, France",
    "tagline": "Communication, marketing, design and media, taught in English",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    **DEPOSIT,
    "tuition_summary": "€8,350 - €10,990 / year",
    "courses": [
        ("Bachelor Event Management", "bachelors", "3 years", 8350, "", _lang("English")),
        ("Bachelor Audiovisual Creation", "bachelors", "3 years", 8350, "", _lang("English")),
        ("Bachelor Digital Marketing & Branding", "bachelors", "3 years", 8350, "", _lang("English")),
        ("Bachelor Graphic Design & Advertising", "bachelors", "3 years", 8350, "", _lang("English")),
        ("Bachelor in Motion Design", "bachelors", "3 years", 8350, "", _lang("English")),
        ("Bachelor in Communication", "bachelors", "3 years", 8350, "", _lang("English")),
        ("MSc in Brand Experience & Events", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Communication & Media Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Performance Marketing & AI Digital Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Corporate Communication & Influence", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Brand Strategy & Artificial Intelligence", "masters", "2 years", 10990, "", _lang("English")),
        ("Master Marketing, Digital Innovation & Media Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in UX/UI Design", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in e-Business and Data Marketing", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Public Relations & Influence", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Strategic Planning & Creative Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Advertising & Media Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Digital Marketing and Social Media Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Events in Cultural & Creative Industries & Brand Experience", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Content Strategy and Copywriting", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Luxury Communication & Media Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Paid Media & Performance", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Event Management & Brand Experience", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Advertising, Visual Content Production & Media Strategy", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Art Direction and Graphic Design", "masters", "2 years", 10990, "", _lang("English")),
        ("MSc in Audiovisual Creation and Production", "masters", "2 years", 10990, "", _lang("English")),
    ],
}

OMNES_SCHOOLS = [ECE, ESCE, INSEEC, HEIP, SUP_DE_PUB]
