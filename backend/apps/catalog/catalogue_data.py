"""The partner catalogue, as supplied by the admissions desk.

This is the seed the platform ships with. Anything added afterwards is added
through **Add course** in the admin, and re-running the seed leaves those
additions alone unless it is asked to prune.

Two things to know about the fees, because they are where a mistake costs money:

* **The application fee belongs to the school.** Most partners charge a flat
  200,000 NGN. UCAM charges 150 EUR, which is converted at the rate on file. The
  fee an applicant pays is read from the school they chose and from nowhere else.
* **The tuition deposit is not collected here.** It is what the school asks for
  once an offer is made, recorded so the applicant can be told what is coming.

Where the supplied list had a problem it is marked with a NOTE, never guessed at
silently. Courses with no tuition figure are stored as None and show as
"On request" rather than as zero.
"""

# ── Destinations ────────────────────────────────────────────────────

COUNTRIES = [
    {"name": "Spain", "code": "ES", "currency": "EUR", "symbol": "€", "european": True, "order": 0},
    {"name": "France", "code": "FR", "currency": "EUR", "symbol": "€", "european": True, "order": 1},
    {"name": "Canada", "code": "CA", "currency": "CAD", "symbol": "C$", "european": False, "order": 2},
]

NGN_FEE = {"fee": 200000, "fee_currency": "NGN"}
EUR_FEE_150 = {"fee": 150, "fee_currency": "EUR"}

# ── Spain ───────────────────────────────────────────────────────────

INSA = {
    "name": "INSA Business School",
    "slug": "insa-business-school",
    "country": "Spain",
    "location": "Barcelona, Spain",
    "tagline": "Business, marketing and technology masters",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    "deposit_percent": 50,
    "tuition_summary": "€4,900 - €11,900 / year",
    "courses": [
        ("Bachelor's Degree in International Business", "bachelors", "3 years", 7500),
        ("Bachelor's Degree in Business and Marketing", "bachelors", "3 years", 7500),
        ("Master in Artificial Intelligence, Data and Cloud", "masters", "1 year", 4900),
        ("Master in International Business Communication", "masters", "1 year", 11900),
        ("Lifelong Learning Master in Business Event Management", "masters", "1 year", 4900),
        ("International MBA", "masters", "1 year", 11900),
        ("Master in Digital Marketing and Customer Experience", "masters", "1 year", 6500),
        # NOTE: supplied as "Master Vin business management"; read as "in".
        ("Master in Business Management", "masters", "1 year", 6500),
        # NOTE: supplied as "Master Vin project management"; read as "in".
        ("Master in Project Management", "masters", "1 year", 6500),
        ("Master in Business Administration", "masters", "1 year", 6500),
        ("Master in Integral Logistics Operations and Supply Chain Management", "masters", "1 year", 6500),
        ("Master in Business Communication", "masters", "1 year", 7400),
        ("Master in Marketing Digital y Social Media", "masters", "1 year", 4900),
        ("Master in Marketing Management", "masters", "1 year", 6500),
        ("Master in Entrepreneurship and Innovation", "masters", "1 year", 4900),
        ("Master in Big Data and Data Intelligence", "masters", "1 year", 4900),
        ("Master in Foreign Trade and International Marketing", "masters", "1 year", 6500),
        ("Master in Business Sustainability Management", "masters", "1 year", 6500),
        ("Master in Digital Business Transformation", "masters", "1 year", 6500),
        ("Master in Data Visualization Management", "masters", "1 year", 6500),
        # NOTE: supplied as "Master i. Logistics"; read as "in".
        ("Master in Logistics", "masters", "1 year", 6500),
    ],
}

C3S = {
    "name": "C3S Business School",
    "slug": "c3s-business-school",
    "country": "Spain",
    "location": "Barcelona, Spain",
    "tagline": "OTHM and NCC accredited diplomas, degrees and masters",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    "deposit_percent": 50,
    "tuition_summary": "€7,000 - €11,000 / year",
    "courses": [
        ("OTHM Level 5 Diploma in Business Management", "diplomas", "1 year", 7000, "October"),
        ("Diploma in Hospitality Management", "diplomas", "1 year", 7000, "October"),
        ("Diploma in Information Technology", "diplomas", "1 year", 7000, "October"),
        ("BA (Hons) in Management", "bachelors", "3 years", 8500, "February, May & October"),
        # NOTE: "BA (Hons) in Business Analytics and Digital Transformation" was
        # listed twice with identical detail; kept once.
        ("BA (Hons) in Business Analytics and Digital Transformation", "bachelors", "3 years", 8500, "February, May & October"),
        ("BA (Hons) in Business Management (Finance and Tech Compliance)", "bachelors", "3 years", 8500, "February, May & October"),
        ("BA (Hons) in Business Management (Entrepreneurship)", "bachelors", "3 years", 8500, "February, May & October"),
        ("BA (Hons) in Business Management (International Business and Cross-Border Trade)", "bachelors", "3 years", 8500, "February, May & October"),
        ("BA (Hons) in Business Computing & Information Systems (NCC)", "bachelors", "3 years", 8500, "February, May & October"),
        ("BA (Hons) in Tourism", "bachelors", "3 years", 8500, "February, May & October"),
        ("Global MBA", "masters", "1 year", 11000, "February, May & October"),
        ("Master in Business Analytics & Data Science for Management", "masters", "1 year", 11000, "February, May & October"),
        ("Master in Entrepreneurship & Business Transformation", "masters", "1 year", 11000, "February, May & October"),
        ("Master in Project Management", "masters", "1 year", 11000, "February, May & October"),
    ],
}

UCAM = {
    "name": "UCAM Universidad Católica de Murcia",
    "slug": "ucam-universidad",
    "country": "Spain",
    "location": "Murcia, Spain",
    "tagline": "One of Spain's most innovative private universities, with degrees across medicine, sport, law and technology",
    "badge": "Partner University",
    "currency": "EUR",
    # The only partner that does not charge the flat Naira fee. Quoted in euros
    # and converted at the rate on file when the applicant is shown it.
    **EUR_FEE_150,
    "deposit_percent": 50,
    "tuition_summary": "€1,300 - €15,200 / year",
    "courses": [
        # Bachelors
        ("Bachelor in Business Administration and Management", "bachelors", "4 years", 6750),
        ("Bachelor in Biotechnology", "bachelors", "4 years", 8100),
        # NOTE: no tuition supplied.
        ("Bachelor in Business Administration", "bachelors", "4 years", None),
        ("Bachelor in Physical Activity & Sport", "bachelors", "4 years", 5990),
        ("Bachelor in Criminology", "bachelors", "4 years", 4990),
        ("Bachelor in Dance", "bachelors", "3 years", 5000),
        ("Bachelor's Degree in Dentistry", "bachelors", "4 years", 15200),
        ("Degree in Law", "bachelors", "4 years", 6500),
        ("Degree in Early Childhood Education", "bachelors", "4 years", 5500),
        # NOTE: no tuition supplied.
        ("Bachelor's in Advertising and Public Relations", "bachelors", "4 years", None),
        ("Bachelor's Degree in Audiovisual Communication", "bachelors", "4 years", 5800),
        ("Bachelor's Degree in Journalism", "bachelors", "4 years", 5800),
        # NOTE: no tuition supplied.
        ("Bachelor's Degree in Advertising, Public Relations & Content Marketing", "bachelors", "4 years", None),
        ("Bachelor's Degree in Marketing & Commercial Management", "bachelors", "4 years", 6200),
        ("Bachelor's Degree in Tourism", "bachelors", "4 years", 6200),
        ("Bachelor's Degree in Psychology", "bachelors", "4 years", 7950),
        ("Bachelor's Degree in Primary Education", "bachelors", "4 years", 5500),
        ("Bachelor's Degree in Translation & Interpretation", "bachelors", "4 years", 5900),
        ("Bachelor's Degree in Medicine", "bachelors", "6 years", 15150),
        ("Bachelor's Degree in Nursing", "bachelors", "4 years", 10500),
        ("Bachelor's Degree in Food Science & Technology", "bachelors", "4 years", 5400),
        ("Bachelor's Degree in Gastronomy", "bachelors", "4 years", 6450),
        # NOTE: no tuition supplied.
        ("Bachelor's Degree in Human Nutrition and Dietetics", "bachelors", "4 years", None),
        ("Bachelor's Degree in Pharmacy", "bachelors", "5 years", 9450),
        ("Bachelor's Degree in Physiotherapy", "bachelors", "4 years", 10000),
        ("Bachelor's Degree in Fundamentals of Architecture", "bachelors", "5 years", 6200),
        ("Degree in Civil Engineering", "bachelors", "4 years", 5990),
        ("Degree in Computer Engineering", "bachelors", "4 years", 5990),
        ("Degree in Building Engineering (Technical Architecture, Spanish)", "bachelors", "4 years", 5990),
        ("Degree in Telecommunications Engineering (Spanish)", "bachelors", "4 years", 5550),
        # NOTE: no tuition supplied.
        ("Bachelor's Degree in International Relations", "bachelors", "4 years", None),
        # NOTE: supplied as "Degree in Modern Language End-of-life Program 4years
        # Care 4years 4,900" - two entries appear to have run together. Recorded
        # as the end-of-life care programme at the figure given.
        ("Degree in End-of-Life Care", "bachelors", "4 years", 4900),
        ("Degree in Marketing & Sales Management", "bachelors", "4 years", 6200),
        # NOTE: listed separately from the 6-year "Bachelor's Degree in Medicine"
        # at the same tuition. Kept as supplied.
        ("Degree in Medicine", "bachelors", "5 years", 15150),
        ("Degree in Human Nutrition & Dietetics (Spanish)", "bachelors", "4 years", 6600),
        # NOTE: a second dentistry entry at a different tuition to the 15,200 one.
        ("Degree in Dentistry", "bachelors", "4 years", 14500),
        ("Degree in Journalism", "bachelors", "4 years", 5800),
        ("Bachelor's Degree in Sport and Exercise Sciences", "bachelors", "4 years", 7800),
        ("Degree in Chiropody", "bachelors", "4 years", 7900),
        # NOTE: no tuition supplied.
        ("Degree in Occupational Therapy", "bachelors", "4 years", None),
        ("Degree in Translation and Interpretation (Spanish)", "bachelors", "4 years", 5900),
        ("Degree in Tourism and Management of Tourism Business (Spanish)", "bachelors", "4 years", 4250),
        ("Bachelor's Degree in Veterinary Medicine", "bachelors", "5 years", 12990),
        # Masters
        ("Master's Degree in Access to the Professions of Lawyer and Solicitor (Spanish)", "masters", "2 years", 4500),
        ("Master's Degree in Architecture (Spanish)", "masters", "1 year", 4850),
        ("Master's Degree in Audiology and Balance (Spanish)", "masters", "1 year", 4800),
        ("Master's Degree in Bilingual Education (Spanish)", "masters", "1 year", 5500),
        ("Master's Degree in Business Administration, MBA (Spanish)", "masters", "1 year", 10200),
        ("Master's Degree in Foot Surgery for Podiatrists (Spanish)", "masters", "1 year", 9500),
        ("Master's Degree in Development, Management and Sustainable Tourism Policy (Spanish)", "masters", "1 year", 4900),
        ("Master's Degree in Development, Management and Sustainable Tourism Policy", "masters", "1 year", 6100),
        ("Master's Degree in Management and Administration of Sports Entities (Spanish)", "masters", "1 year", 6500),
        ("Master's Degree in Emergency, Urgent Care and Special Care Nursing (Spanish)", "masters", "1 year", 6750),
        ("Master's Degree in School Nursing and Health", "masters", "1 year", 4100),
        ("Master's Degree in High Performance Sports: Strength and Physical Conditioning", "masters", "1 year", 7500),
        ("Master's Degree in Architecture", "masters", "1 year", 4850),
        ("Master's Degree in Audiology and Balance", "masters", "2 years", 4850),
        ("Master's Degree in Management and Administration of Sports Entities", "masters", "1 year", 6500),
        ("Master's Degree in Physical Exercise and Training for Health", "masters", "1 year", 4500),
        ("Master's Degree in Bilingual Education: English (CLIL)", "masters", "1 year", 5500),
        ("Master's Degree in Physiotherapy in Sport", "masters", "1 year", 7100),
        ("Master's Degree in Teacher Training", "masters", "1 year", 7050),
        ("Master's Degree in Geriatrics and Gerontology: Comprehensive Care for Dependency", "masters", "1 year", 5500),
        ("Master's Degree in Management and Planning of Health Services", "masters", "1 year", 7300),
        ("Master's Degree in High Performance Sport: Strength and Conditioning", "masters", "1 year", 9300),
        ("Master's Degree in Hospitality Management", "masters", "1 year", 7600),
        ("Master's Degree in Civil Engineering", "masters", "2 years", 5700),
        ("Master's Degree in Innovation and Tourism Marketing", "masters", "1 year", 6800),
        ("Master's Degree in Research in Physical Education and Health", "masters", "1 year", 5200),
        ("Master's Degree in Management of Sport Entities", "masters", "1 year", 11700),
        ("Master's Degree in Marketing and Communication", "masters", "1 year", 7800),
        ("Master's Degree in Emergency Medicine", "masters", "1 year", 7000),
        ("Master's Degree in Clinical Nutrition", "masters", "1 year", 6500),
        ("Master's Degree in Nutrition in Physical Activity and Sport (Blended Learning)", "masters", "1 year", 7300),
        ("Master's Degree in Nutrition and Food Security (Blended Learning)", "masters", "1 year", 4800),
        ("Master's Degree in Osteopathy and Manual Therapy (Blended Learning)", "masters", "2 years", 11950),
        ("Master's Degree in General Health Psychology", "masters", "2 years", 14100),
        ("Master's Degree in Corporate Social Responsibility", "masters", "1 year", 4350),
        ("Master's Degree in Voice, Language and Communication Disorders", "masters", "1 year", 4150),
        ("Master's Degree in Continuing Education Composition for VFX (Blended Learning)", "masters", "1 year", 8500),
        ("Master's Degree in International Relations", "masters", "1 year", 5500),
        ("Master's Degree in MBA in Sports Management", "masters", "1 year", 8980),
        ("Master's Degree in Continuing Education Digital Marketing & Strategy (Blended Learning)", "masters", "9 months", 4000),
        ("Master's Degree in Continuing Education BIM/GIS Methodology, Programming & Data Governance (Blended Learning)", "masters", "9 months", 3800),
        ("Master's Degree in Clinical and Sports Podiatry (Blended Learning)", "masters", "1 year", 4600),
        ("Master's Degree in Physical Preparation and Sports Rehabilitation in Football", "masters", "1 year", 7990),
        ("Master's Degree in Continuing Education Music Production", "masters", "1 year", 3900),
        ("Master's Degree in MBA Sport Management", "masters", "1 year", 11700),
        ("Master's Degree in Continuing Education Digital Transformation of the Agriculture Sector (Blended Learning)", "masters", "1 year", 4300),
        ("Master's Degree in Continuing Education Sport Traumatology", "masters", "2 years", 8500),
        ("Master's Degree in Continuing Education Graphic Design On/Offline", "masters", "1 year", 5500),
        ("Master's Degree in Corporate Tax Consulting", "masters", "9 months", 4500),
        ("Master's Degree in Big Data & Data Engineering", "masters", "9 months", 4100),
        ("Executive Master in Financial Management", "masters", "9 months", 4100),
        # Doctoral. Tuition is per year, which the note records.
        ("PhD in Social Sciences", "phd", "3 years", 1800, "", "€1,800 per year"),
        ("PhD in Health Sciences", "phd", "3 years", 1300, "", "€1,300 per year"),
        ("PhD in Sports Sciences", "phd", "3 years", 1300, "", "€1,300 per year"),
        ("PhD in Computer Technologies and Environmental Engineering", "phd", "3 years", 1300, "", "€1,300 per year"),
    ],
}

# ── France ──────────────────────────────────────────────────────────
#
# These four quote a total for the programme and a first-year figure, with 690
# EUR of other expenses on top. `tuition` is the first-year figure, because that
# is what an applicant pays to start; the note carries the total and the extras.

PBA = {
    "name": "Paris Business Academy (PBA)",
    "slug": "paris-business-academy",
    "country": "France",
    "location": "Paris, France",
    "tagline": "State-recognised RNCP Level 6 and 7 degrees in business and digital",
    "badge": "Premier Partner",
    "currency": "EUR",
    **NGN_FEE,
    "tuition_summary": "€7,500 - €12,000 first year",
    "courses": [
        ("Bachelor's in Web Marketing", "bachelors", "3 Years", 10000, "September / October & January", "€10,000 per year + €690 other expenses", "Level 6 (RNCP35634)", "25% scholarship: €7,500/yr + €690 other expenses"),
        ("Bachelor's in Digital Project Management", "bachelors", "3 Years", 10000, "September / October & January", "€10,000 per year + €690 other expenses", "Level 6 (RNCP35634)", "25% scholarship: €7,500/yr + €690 other expenses"),
        ("Bachelor's in Web Development", "bachelors", "3 Years", 10000, "September / October & January", "€10,000 per year + €690 other expenses", "Level 6 (RNCP35634)", "25% scholarship: €7,500/yr + €690 other expenses"),
        ("Global MBA", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP41354)", "25% scholarship: €9,000 + €690 other expenses"),
        ("Mastère in Business Project Management", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP41354)", "25% scholarship: €9,000 + €690 other expenses"),
    ],
}

FINANCIA = {
    "name": "Financia Business School",
    "slug": "financia-business-school",
    "country": "France",
    "location": "Paris, France",
    "tagline": "Specialist finance and management school with RNCP accredited degrees and MBAs",
    "badge": "Finance Specialist",
    "currency": "EUR",
    **NGN_FEE,
    "tuition_summary": "€10,000 - €12,000 first year",
    "courses": [
        ("Bachelor in Business Development", "bachelors", "3 Years", 10000, "September / October & January", "€10,000 per year + €690 other expenses", "Level 6 (RNCP40889, Formatives)"),
        ("MBA Corporate Finance & Financial Control", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP41469)"),
        ("MBA Trading & Finance", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP38601)"),
    ],
}

ALTERNIS = {
    "name": "Alternis Business School",
    "slug": "alternis-business-school",
    "country": "France",
    "location": "Paris, France",
    "tagline": "Work-study and management excellence, RNCP Level 6 and 7 certified",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    "tuition_summary": "€10,000 - €12,000 first year",
    "courses": [
        ("Bachelor in Business Development", "bachelors", "3 Years", 10000, "September / October & January", "€10,000 per year + €690 other expenses", "Level 6 (RNCP40889, Formatives)"),
        ("MBA Logistics, Purchasing and Supply Chain", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP37618, ESLI)"),
    ],
}

HEMA = {
    "name": "HEMA Groupe",
    "slug": "hema-groupe",
    "country": "France",
    "location": "Paris, France",
    "tagline": "A group of specialist schools: ESMA, ISEADD and ISEAM",
    "badge": "Partner School",
    "currency": "EUR",
    **NGN_FEE,
    "tuition_summary": "€10,000 - €12,000 first year",
    "courses": [
        ("Bachelor's in Manager of Business Development (ESMA School)", "bachelors", "3 Years", 10000, "September / October & January", "€10,000 per year + €690 other expenses", "Level 6 (RNCP38602)"),
        ("Mastère in Sustainable Development & CSR (ISEADD School)", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP40654)"),
        ("Mastère in Energy, Environment and Climate Management (ISEADD School)", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP40655)"),
        ("Mastère in Innovative Project Management (ISEAM School)", "masters", "2 Years", 12000, "September / October & January", "Total €18,000. First year €12,000 + €690 other expenses", "Level 7 (RNCP41354)"),
    ],
}

# ── Canada ──────────────────────────────────────────────────────────

SHERIDAN = {
    "name": "Sheridan College",
    "slug": "sheridan-college",
    "country": "Canada",
    "location": "Ontario, Canada",
    "tagline": "Degrees, diplomas and graduate certificates across animation, health, engineering and business",
    "badge": "Partner College",
    "currency": "CAD",
    **NGN_FEE,
    "deposit_percent": 50,
    "tuition_summary": "C$16,954 - C$39,045 / year",
    "courses": [
        # Bachelors
        ("Bachelor in Nursing", "bachelors", "4 years", 26576),
        ("Bachelor of Osteopathy", "bachelors", "4 years", 23099),
        ("Bachelor of Textiles, Craft and Design", "bachelors", "4 years", 21255),
        ("Bachelor in 3D Animation and Emerging Technologies", "bachelors", "4 years", 31227),
        ("Bachelor of Animation, Honours", "bachelors", "4 years", 10353),
        # NOTE: no tuition supplied.
        ("Bachelor of Art and Art History", "bachelors", "4 years", None),
        ("Bachelor of Athletic Therapy, Health Sciences", "bachelors", "4 years", 29108),
        ("Bachelor in Ceramics, Craft and Design", "bachelors", "4 years", 21255),
        ("Bachelor in Computer Science, Mobile Computing", "bachelors", "4 years", 21472),
        ("Bachelor of Computer Science", "bachelors", "4 years", 23011),
        ("Bachelor in Cyber Security, Information Sciences", "bachelors", "4 years", 23824),
        ("Bachelor in Electrical Engineering", "bachelors", "4 years", 23452),
        ("Bachelor in Experiential Design", "bachelors", "4 years", 23960),
        ("Bachelor of Film and Television", "bachelors", "4 years", 29659),
        ("Bachelor of Furniture, Craft and Design", "bachelors", "4 years", 21255),
        ("Bachelor of Game Design", "bachelors", "4 years", 22576),
        ("Bachelor in Glass, Craft and Design", "bachelors", "4 years", 21255),
        # NOTE: no tuition supplied.
        ("Bachelor in Illustration", "bachelors", "4 years", None),
        ("Bachelor in Industrial Design, Craft and Design", "bachelors", "4 years", 21255),
        ("Bachelor in Interaction Design", "bachelors", "4 years", 22424),
        ("Bachelor of Interior Design", "bachelors", "4 years", 24887),
        ("Bachelor in Kinesiology and Health Promotion, Health Sciences", "bachelors", "4 years", 28854),
        ("Bachelor in Music Theatre Performance", "bachelors", "4 years", 39045),
        ("Bachelor in Mechanical Engineering", "bachelors", "4 years", 23243),
        ("Bachelor in Multidisciplinary, Craft and Design", "bachelors", "4 years", 21255),
        ("Honours Bachelor of Early Childhood Leadership", "bachelors", "2 years", 24271),
        # Masters
        ("Master of Animation, Games and Immersive Experiences", "masters", "2 years", 32347),
        # Diplomas
        ("Diploma in Computer Systems Technician, Cyber Security", "diplomas", "2 years", 19701),
        ("Diploma in Educational Support", "diplomas", "2 years", 19901),
        ("Diploma in Electrical Engineering Technician", "diplomas", "2 years", 20329),
        ("Diploma in Computer Systems Technician, Information Technology Infrastructure and Services", "diplomas", "2 years", 19701),
        ("Diploma in Graphic Design, Creative Practice", "diplomas", "2 years", 18756),
        ("Diploma in Accounting, Business", "diplomas", "2 years", 16956),
        ("Diploma in Business", "diplomas", "2 years", 16954),
        ("Diploma in Addictions and Mental Health", "diplomas", "2 years", 19410),
        ("Diploma in CNC & Precision Machining, Mechanical Technician", "diplomas", "2 years", 20587),
        ("Diploma in Advertising and Marketing Communications", "diplomas", "2 years", 19739),
        ("Diploma in Computer Engineering Technician", "diplomas", "2 years", 20364),
        ("Diploma in Computer Programming", "diplomas", "2 years", 19701),
        ("Diploma in Architectural Technician, Sustainable Design", "diplomas", "2 years", 20019),
        ("Diploma in Construction Engineering Technician, Sustainability", "diplomas", "2 years", 21914),
        ("Diploma in General Arts & Science", "diplomas", "2 years", 19671),
        ("Diploma in Industrial Millwright, Mechanical Technician", "diplomas", "2 years", 21684),
        # NOTE: "Diploma in Interior Decorating" was listed twice, identically.
        ("Diploma in Interior Decorating", "diplomas", "2 years", 19859),
        ("Diploma in Makeup for Media and Creative Arts", "diplomas", "2 years", 21360),
        ("Diploma in Marketing, Business", "diplomas", "2 years", 16954),
        ("Diploma in Early Childhood Education", "diplomas", "2 years", 19721),
        ("Diploma in Early Childhood Education, Intensive", "diplomas", "1 year", 19651),
        ("Diploma in Nutrition and Food Service Management", "diplomas", "2 years", 19731),
        ("Diploma in Office Administration, Health Services", "diplomas", "2 years", 19787),
        ("Diploma in Pharmacy Technician", "diplomas", "2 years", 19779),
        ("Diploma in Plumbing Technician", "diplomas", "2 years", 20412),
        ("Diploma in Police Foundations", "diplomas", "2 years", 19823),
        ("Diploma in Practical Nursing", "diplomas", "2 years", 25793),
        ("Diploma in Social Service Worker", "diplomas", "2 years", 19786),
        ("Diploma in Social Service Worker, Gerontology", "diplomas", "2 years", 19886),
        ("Diploma in Welding and Fabrication Technician", "diplomas", "2 years", 20383),
        ("Diploma in Visual and Creative Arts", "diplomas", "2 years", 20535),
        ("Diploma in Veterinary Technician", "diplomas", "2 years", 21205),
        # Advanced diplomas
        ("Advanced Diploma in Technical Production for the Performing Arts Industry", "diplomas", "3 years", 21536),
        ("Advanced Diploma in Network Engineering Technology", "diplomas", "3 years", 19774),
        ("Advanced Diploma in Diagnostic Imaging Technology", "diplomas", "3 years", 21084),
        ("Advanced Diploma in Graphic Design, Creative Strategies", "diplomas", "3 years", 18756),
        ("Advanced Diploma in Computer Systems Technology, Analysis and Design", "diplomas", "3 years", 20019),
        ("Advanced Diploma in Computer Systems Technology, Software Development and Network Engineering", "diplomas", "3 years", 19701),
        ("Advanced Diploma in Child and Youth Care", "diplomas", "3 years", 19769),
        ("Advanced Diploma in Advertising and Marketing Communications, Management", "diplomas", "3 years", 19739),
        ("Advanced Diploma in Architectural Technology, Sustainable Design", "diplomas", "3 years", 20019),
        ("Advanced Diploma in Marketing, Business Administration", "diplomas", "3 years", 16954),
        ("Advanced Diploma in Massage Therapy", "diplomas", "3 years", 18989),
        # Graduate certificates
        ("Graduate Certificate in Artificial Intelligence Development and Applications", "diplomas", "2 years", 20670),
        ("Graduate Certificate in Marketing Management, Digital Strategies", "diplomas", "1 year", 16442),
        ("Graduate Certificate in Internet of Things and Machine Intelligence", "diplomas", "1 year", 18766),
        # NOTE: "Interactive Media Management, Digital Design" was listed twice,
        # identically.
        ("Graduate Certificate in Interactive Media Management, Digital Design", "diplomas", "1 year", 25729),
        ("Graduate Certificate in Music Scoring for Screen and Stage", "diplomas", "1 year", 33769),
        ("Graduate Certificate in Game Development, Advanced Programming", "diplomas", "1 year", 27928),
        ("Graduate Certificate in Digital Product Design", "diplomas", "1 year", 27745),
        ("Graduate Certificate in Financial Technology", "diplomas", "1 year", 20057),
        ("Graduate Certificate in Clinical Kinesiology", "diplomas", "1 year", 18831),
        ("Graduate Certificate in Healthcare Administration and Service Management", "diplomas", "1 year", 21483),
        ("Graduate Certificate in Computer Animation", "diplomas", "1 year", 26641),
        ("Graduate Certificate in Advanced Special Effects Makeup, Prosthetics and Props", "diplomas", "1 year", 27319),
        ("Graduate Certificate in Advanced Television and Film", "diplomas", "1 year", 34246),
        # NOTE: supplied as "19,7667 CAD", which has a digit too many. Recorded as
        # 19,766 and flagged: confirm before this one is quoted to anybody.
        ("Graduate Certificate in Applied Data Analytics and Visualization", "diplomas", "2 years", 19766, "", "Tuition to be confirmed with the college"),
        ("Graduate Certificate in Human Resources Management", "diplomas", "1 year", 21655),
        ("Graduate Certificate in Operational Technology Cybersecurity", "diplomas", "1 year", 19943),
        ("Graduate Certificate in Project Management, Information Technology", "diplomas", "1 year", 19814),
        ("Graduate Certificate in Supply Chain Management, Logistics Automation", "diplomas", "1 year", 18541),
        ("Graduate Certificate in Urban Design", "diplomas", "1 year", 18639),
        ("Graduate Certificate in Visual Effects", "diplomas", "1 year", 26641),
        # Certificates
        ("Certificate in Welding Techniques", "diplomas", "1 year", 20383),
        ("Certificate in Personal Support Worker", "diplomas", "1 year", 20933),
        ("Certificate in Plumbing, Mechanical Techniques", "diplomas", "1 year", 20412),
        ("Certificate in Pre-Health Sciences Pathway to Advanced Diplomas and Degrees", "diplomas", "1 year", 19756),
        ("Certificate in Construction Techniques", "diplomas", "1 year", 21327),
        ("Certificate in Media Fundamentals", "diplomas", "1 year", 19988),
        # NOTE: "Certificate in Electrical Techniques" was listed twice, identically.
        ("Certificate in Electrical Techniques", "diplomas", "1 year", 20329),
        ("Certificate in CNC & Precision Machining, Mechanical Techniques", "diplomas", "1 year", 20587),
        ("Certificate in Animal Care", "diplomas", "1 year", 20118),
    ],
}

CIMT = {
    "name": "CIMT College",
    "slug": "cimt-college",
    "country": "Canada",
    "location": "Ontario, Canada",
    "tagline": "Short diploma programmes for international students, under six months and without a practicum",
    "badge": "Partner College",
    "currency": "CAD",
    **NGN_FEE,
    # The only partner with a flat deposit rather than a share of tuition.
    "deposit_amount": 500,
    "tuition_summary": "Short programmes, tuition on request",
    "courses": [
        # NOTE: no tuition or duration supplied for these, so they are recorded as
        # on request. The duration note is the college's own condition.
        ("Artificial Intelligence", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Business Administration", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Cabinetry and Furniture Technician", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Data Science and Big Data", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Deep Learning", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Dental Office Administration", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Legal Office Administration", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Machine Learning", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
        ("Medical Office Administration", "diplomas", "Under 6 months", None, "", "Short diploma programme, no practicum"),
    ],
}

SCHOOLS = [INSA, C3S, UCAM, PBA, FINANCIA, ALTERNIS, HEMA, SHERIDAN, CIMT]


def course_fields(row):
    """One course row as keyword arguments.

    Rows are tuples so the data above stays readable down the page. The trailing
    fields are optional, in this order: intake, note, accreditation, scholarship.
    """
    name, level, duration, tuition = row[0], row[1], row[2], row[3]
    intake = row[4] if len(row) > 4 else ""
    note = row[5] if len(row) > 5 else ""
    qualification = row[6] if len(row) > 6 else ""
    scholarship = row[7] if len(row) > 7 else ""
    return {
        "name": name,
        "level": level,
        "duration": duration,
        "tuition": tuition,
        "intake": intake,
        "note": note,
        "qualification_level": qualification,
        "scholarship": scholarship,
    }
