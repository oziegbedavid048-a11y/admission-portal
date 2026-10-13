"""Seed a realistic test agent account with authentic earning history and admission letters.

Earning rules:
- Registration commission: N30,000 per student once application fee is confirmed
- Visa commission: N50,000 once student visa is approved and verified
- Available balance: N2,140,000 (over 2 Million Naira)
- Official letters: Admission letters only (Letter.Kind.ADMISSION)
- Loans: Ads funding history with 2 repaid loans (N150,000 total repaid) and 1 declined loan
- Withdrawals: 2 completed payouts (N500,000 total)
- Active debt: N0.00

Every account it creates is marked as a test account, so none of it shows on the
real admin screens. It is listed under "Test accounts" in the admin instead, and
no email is sent to any of it.
"""

from datetime import timedelta
from decimal import Decimal
import io
import os
import uuid

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import pre_save
from django.utils import timezone
import pypdf

from apps.accounts.models import User
from apps.applications.models import (
    Application,
    Document,
    Letter,
    Stage,
)
from apps.applications.constants import (
    AGENT_REGISTRATION_COMMISSION_NGN,
    AGENT_VISA_COMMISSION_NGN,
)
from apps.catalog.models import (
    DestinationCountry,
    Institution,
    OriginCountry,
    Program,
)
from apps.partners.models import (
    AgentProfile,
    Commission,
    Loan,
    LoanRepayment,
    StudentDraft,
    Wallet,
    Withdrawal,
)
from apps.payments.models import Payment

def _make_sample_pdf():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

SAMPLE_PDF_BYTES = _make_sample_pdf()

NIGERIAN_STUDENTS = [
    ("Chioma Blessing Eze", "chioma.eze.student@gmail.com", "+2348021122301", "Bachelor's Degree", "Second Class Upper (4.2/5.0)"),
    ("Babatunde Ayodele Adeleke", "babatunde.adeleke.student@gmail.com", "+2348032233402", "Master's Degree", "Distinction"),
    ("Amina Zainab Usman", "amina.usman.student@gmail.com", "+2348053344503", "Bachelor's Degree", "First Class Honours (4.8/5.0)"),
    ("Emeka Victor Nnamdi", "emeka.nnamdi.student@gmail.com", "+2348064455604", "HND", "Upper Credit"),
    ("Damilola Sarah Oladipo", "damilola.oladipo.student@gmail.com", "+2348075566705", "Bachelor's Degree", "Second Class Upper (4.3/5.0)"),
    ("Ifeanyi Samuel Okorie", "ifeanyi.okorie.student@gmail.com", "+2348086677806", "Bachelor's Degree", "Second Class Upper (4.1/5.0)"),
    ("Favour Temitope Ajayi", "favour.ajayi.student@gmail.com", "+2348097788907", "Bachelor's Degree", "Second Class Upper (3.9/5.0)"),
    ("Olumide Kazeem Sanusi", "olumide.sanusi.student@gmail.com", "+2348108899008", "SSCE / High School", "6 Credits (WAEC)"),
    ("Ngozi Cynthia Onyekwere", "ngozi.onyekwere.student@gmail.com", "+2348119900109", "Master's Degree", "Merit"),
    ("Chidiebere Collins Umeh", "chidiebere.umeh.student@gmail.com", "+2348120011210", "Bachelor's Degree", "Second Class Lower (3.2/5.0)"),
    ("Aisha Maryam Bello", "aisha.bello.student@gmail.com", "+2348131122311", "Bachelor's Degree", "Second Class Upper (4.4/5.0)"),
    ("Tobi Joshua Fashola", "tobi.fashola.student@gmail.com", "+2348142233412", "Bachelor's Degree", "Second Class Upper (4.0/5.0)"),
    ("Somtochukwu David Madu", "somto.madu.student@gmail.com", "+2348153344513", "HND", "Upper Credit"),
    ("Kehinde Paul Alabi", "kehinde.alabi.student@gmail.com", "+2348164455614", "Bachelor's Degree", "Second Class Lower (3.4/5.0)"),
    ("Precious Nkechi Obi", "precious.obi.student@gmail.com", "+2348175566715", "SSCE / High School", "7 Credits (NECO)"),
    ("Halima Fatima Danjuma", "halima.danjuma.student@gmail.com", "+2348186677816", "Bachelor's Degree", "First Class Honours (4.7/5.0)"),
    ("Osasere Godstime Ighodaro", "osasere.ighodaro.student@gmail.com", "+2348197788917", "Bachelor's Degree", "Second Class Upper (3.8/5.0)"),
    ("Chiamaka Grace Nwosu", "chiamaka.nwosu.student@gmail.com", "+2348208899018", "OND", "Upper Credit"),
    ("Adeola Motunrayo Bakare", "adeola.bakare.student@gmail.com", "+2348011223319", "Bachelor's Degree", "Second Class Upper (4.1/5.0)"),
    ("Chinedu Stanley Okoli", "chinedu.okoli.student@gmail.com", "+2348022334420", "Master's Degree", "Distinction"),
    ("Zubairu Mohammed Tanko", "zubairu.tanko.student@gmail.com", "+2348033445521", "Bachelor's Degree", "Second Class Upper (4.2/5.0)"),
    ("Folashade Elizabeth Agboola", "folashade.agboola.student@gmail.com", "+2348044556622", "Bachelor's Degree", "Second Class Upper (4.0/5.0)"),
    ("Kelechi Augustine Ibe", "kelechi.ibe.student@gmail.com", "+2348055667723", "HND", "Upper Credit"),
    ("Bilikisu Hauwa Umar", "bilikisu.umar.student@gmail.com", "+2348066778824", "Bachelor's Degree", "Second Class Upper (4.3/5.0)"),
    ("Opeyemi Daniel Ogundipe", "opeyemi.ogundipe.student@gmail.com", "+2348077889925", "Master's Degree", "Merit"),
    ("Nnenna Jennifer Chukwu", "nnenna.chukwu.student@gmail.com", "+2348088990026", "Bachelor's Degree", "Second Class Upper (4.5/5.0)"),
    ("Mubarak Sani Garba", "mubarak.garba.student@gmail.com", "+2348099001127", "Bachelor's Degree", "First Class Honours (4.6/5.0)"),
    ("Simisola Joy Adelegan", "simisola.adelegan.student@gmail.com", "+2348100112228", "Bachelor's Degree", "Second Class Upper (4.1/5.0)"),
    ("Chukwuma Francis Okafor", "chukwuma.okafor.student@gmail.com", "+2348111223329", "Bachelor's Degree", "Second Class Upper (3.9/5.0)"),
    ("Hadiza Kabir Abubakar", "hadiza.abubakar.student@gmail.com", "+2348122334430", "Bachelor's Degree", "Second Class Upper (4.2/5.0)"),
    ("Kayode Victor Adeleke", "kayode.adeleke.student@gmail.com", "+2348133445531", "Master's Degree", "Distinction"),
    ("Chinelo Stephanie Ude", "chinelo.ude.student@gmail.com", "+2348144556632", "Bachelor's Degree", "Second Class Upper (4.0/5.0)"),
    ("Yakubu Aliyu Gwandu", "yakubu.gwandu.student@gmail.com", "+2348155667733", "HND", "Upper Credit"),
    ("Yetunde Omolara Salami", "yetunde.salami.student@gmail.com", "+2348166778834", "Bachelor's Degree", "Second Class Upper (4.4/5.0)"),
    ("Uchechukwu Anthony Ezenwa", "uche.ezenwa.student@gmail.com", "+2348177889935", "Bachelor's Degree", "Second Class Lower (3.3/5.0)"),
    ("Rukayat Toyin Gbadamosi", "rukayat.gbadamosi.student@gmail.com", "+2348188990036", "Bachelor's Degree", "Second Class Upper (3.8/5.0)"),
    ("Bashir Idris Galadima", "bashir.galadima.student@gmail.com", "+2348199001137", "Bachelor's Degree", "Second Class Upper (4.1/5.0)"),
    ("Nkiruka Vivian Anyanwu", "nkiruka.anyanwu.student@gmail.com", "+2348200112238", "Master's Degree", "Merit"),
    ("Ayomide Sunday Ojo", "ayomide.ojo.student@gmail.com", "+2348211223339", "Bachelor's Degree", "Second Class Upper (4.0/5.0)"),
    ("Onyinyechi Faith Mbah", "onyinyechi.mbah.student@gmail.com", "+2348222334440", "Bachelor's Degree", "Second Class Upper (4.2/5.0)"),
    ("Abba Mustapha Kyari", "abba.kyari.student@gmail.com", "+2348233445541", "HND", "Upper Credit"),
    ("Eniola Bukola Shonibare", "eniola.shonibare.student@gmail.com", "+2348244556642", "Bachelor's Degree", "Second Class Upper (3.9/5.0)"),
    ("Ebuka Christian Nwankwo", "ebuka.nwankwo.student@gmail.com", "+2348255667743", "Bachelor's Degree", "Second Class Upper (4.3/5.0)"),
    ("Maryam Bello Farouk", "maryam.farouk.student@gmail.com", "+2348266778844", "Bachelor's Degree", "Second Class Upper (4.1/5.0)"),
    ("Gbolahan Segun Taiwo", "gbolahan.taiwo.student@gmail.com", "+2348277889945", "SSCE / High School", "6 Credits (WAEC)"),
    ("Amarachi Hope Kalu", "amarachi.kalu.student@gmail.com", "+2348288990046", "Bachelor's Degree", "Second Class Lower (3.4/5.0)"),
    ("Suleiman Jibril Bawa", "suleiman.bawa.student@gmail.com", "+2348299001147", "Bachelor's Degree", "Second Class Upper (3.8/5.0)"),
    ("Oluwatobi Felix Adesina", "oluwatobi.adesina.student@gmail.com", "+2348300112248", "Bachelor's Degree", "Second Class Upper (4.0/5.0)"),
]


class Command(BaseCommand):
    help = "Seeds a test agent account with authentic earning history and admission letters."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="chukwuemeka.okonkwo@gmail.com",
            help="Email address for the test agent.",
        )
        parser.add_argument(
            "--password",
            default="AgentPass2026!",
            help="Password for the test agent.",
        )
        parser.add_argument(
            "--name",
            default="Chukwuemeka Kingsley Okonkwo",
            help="Full name of the agent.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        full_name = options["name"].strip()
        phone = "+2348035678912"
        agency_name = "Okonkwo Global Education & Travel Consult"

        self.stdout.write(f"Setting up test agent account: {email}...")

        # Disconnect heavy pre-save compression signals during seeding to ensure fast execution
        try:
            from apps.applications import compression
            pre_save.disconnect(sender=Document, dispatch_uid=f"compress-{Document._meta.label_lower}")
            pre_save.disconnect(sender=Letter, dispatch_uid=f"compress-{Letter._meta.label_lower}")
        except Exception:
            pass

        try:
            self._seed(email, password, full_name, phone, agency_name)
        finally:
            # Reconnect compression signals
            try:
                from apps.applications import compression
                compression.connect()
            except Exception:
                pass

    @transaction.atomic
    def _seed(self, email, password, full_name, phone, agency_name):
        # 1. User Account
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "phone": phone,
                "role": User.Role.AGENT,
                "country": "Nigeria",
                "email_verified": True,
                "is_active": True,
                "is_test_account": True,
            },
        )
        user.full_name = full_name
        user.phone = phone
        user.role = User.Role.AGENT
        user.country = "Nigeria"
        user.email_verified = True
        user.is_active = True
        # Keeps this account and everything it owns off the real admin screens.
        user.is_test_account = True
        user.set_password(password)
        user.save()

        # 2. Agent Profile
        profile, _ = AgentProfile.objects.get_or_create(
            user=user,
            defaults={
                "agency_name": agency_name,
                "bank_name": "Zenith Bank",
                "account_number": "2109876543",
                "account_name": full_name,
                "total_closed_sales": 28,
            },
        )
        profile.agency_name = agency_name
        profile.bank_name = "Zenith Bank"
        profile.account_number = "2109876543"
        profile.account_name = full_name
        profile.total_closed_sales = 28
        profile.save()

        # Clean slate for previous agent relations
        Application.objects.filter(submitted_by_agent=profile).delete()
        Loan.objects.filter(agent=profile).delete()
        LoanRepayment.objects.filter(agent=profile).delete()
        Withdrawal.objects.filter(agent=profile).delete()
        Commission.objects.filter(agent=profile).delete()
        StudentDraft.objects.filter(agent=profile).delete()

        # Countries & Catalogs
        origin_nigeria, _ = OriginCountry.objects.get_or_create(
            name="Nigeria",
            defaults={"currency": "NGN", "symbol": "₦", "ngn_per_unit": Decimal("1")},
        )
        dest_spain = DestinationCountry.objects.filter(name__iexact="Spain").first()
        dest_france = DestinationCountry.objects.filter(name__iexact="France").first()
        dest_italy = DestinationCountry.objects.filter(name__iexact="Italy").first()
        dest_malta = DestinationCountry.objects.filter(name__iexact="Malta").first()
        dest_canada = DestinationCountry.objects.filter(name__iexact="Canada").first()

        destinations = [d for d in [dest_spain, dest_france, dest_italy, dest_malta, dest_canada] if d]
        if not destinations:
            dest_spain, _ = DestinationCountry.objects.get_or_create(name="Spain", defaults={"code": "ES", "currency": "EUR"})
            destinations = [dest_spain]

        institutions = list(Institution.objects.all())
        programs = list(Program.objects.all())
        now = timezone.now()

        # 3. Create 48 Students:
        # - Indices 0..27 (28 students): Admitted, Visa Completed (Earn 30k reg + 50k visa = 80k each)
        # - Indices 28..35 (8 students): Admitted, Visa In Progress (Earn 30k reg only)
        # - Indices 36..41 (6 students): Admitted, Visa Not Started (Earn 30k reg only)
        # - Indices 42..45 (4 students): In Review (Earn 30k reg only)
        # - Indices 46..47 (2 students): Submitted (Earn 30k reg only)
        # All admitted students (indices 0..41 -> 42 students) get an Official Letter of Admission (Admission letters only!)
        reg_comm_total = Decimal("0.00")
        visa_comm_total = Decimal("0.00")

        reg_amount = AGENT_REGISTRATION_COMMISSION_NGN  # 30,000 NGN
        visa_amount = AGENT_VISA_COMMISSION_NGN        # 50,000 NGN

        for idx, (s_name, s_email, s_phone, s_qual, s_grade) in enumerate(NIGERIAN_STUDENTS):
            applicant_user, _ = User.objects.get_or_create(
                email=s_email,
                defaults={
                    "full_name": s_name,
                    "phone": s_phone,
                    "role": User.Role.APPLICANT,
                    "country": "Nigeria",
                    "email_verified": True,
                    "is_active": True,
                    "is_test_account": True,
                },
            )
            applicant_user.full_name = s_name
            applicant_user.is_test_account = True
            applicant_user.set_password("StudentPass2026!")
            applicant_user.save()

            if idx < 28:
                status = Application.Status.ADMITTED
                visa_status = Application.VisaStatus.COMPLETED
                verification_status = Application.VerificationStatus.VERIFIED
                days_ago = 180 - (idx * 4)
            elif idx < 36:
                status = Application.Status.ADMITTED
                visa_status = Application.VisaStatus.IN_PROGRESS
                verification_status = Application.VerificationStatus.VERIFIED
                days_ago = 68 - ((idx - 28) * 4)
            elif idx < 42:
                status = Application.Status.ADMITTED
                visa_status = Application.VisaStatus.NOT_STARTED
                verification_status = Application.VerificationStatus.VERIFIED
                days_ago = 36 - ((idx - 36) * 4)
            elif idx < 46:
                status = Application.Status.IN_REVIEW
                visa_status = Application.VisaStatus.NOT_STARTED
                verification_status = Application.VerificationStatus.IN_REVIEW
                days_ago = 12 - ((idx - 42) * 2)
            else:
                status = Application.Status.SUBMITTED
                visa_status = Application.VisaStatus.NOT_STARTED
                verification_status = Application.VerificationStatus.UNVERIFIED
                days_ago = 3 - (idx - 46)

            submitted_dt = now - timedelta(days=days_ago)
            dest_choice = destinations[idx % len(destinations)]
            inst_choice = institutions[idx % len(institutions)] if institutions else None

            app = Application.objects.create(
                applicant=applicant_user,
                submitted_by_agent=profile,
                full_name=s_name,
                email=s_email,
                phone=s_phone,
                address="Plot 14 Victoria Island, Lagos, Nigeria",
                origin_country=origin_nigeria,
                destination_country=dest_choice,
                institution=inst_choice,
                qualification=s_qual,
                grade_gpa=s_grade,
                year_graduated=2023,
                status=status,
                visa_status=visa_status,
                transferred_to_visa_support=(visa_status != Application.VisaStatus.NOT_STARTED),
                transferred_to_visa_support_at=(submitted_dt + timedelta(days=20)) if (visa_status != Application.VisaStatus.NOT_STARTED) else None,
                verification_status=verification_status,
                personal_details_verified=(status == Application.Status.ADMITTED),
                academic_details_verified=(status == Application.Status.ADMITTED),
                submitted_at=submitted_dt,
            )

            if programs:
                prog_choice = programs[idx % len(programs)]
                app.programs.add(prog_choice)

            # Build default timeline stages
            app.build_default_stages(first_note="Application submitted and verified.")
            if status == Application.Status.ADMITTED:
                app.stages.all().update(status=Stage.Status.COMPLETED)
            elif status == Application.Status.IN_REVIEW:
                stages = list(app.stages.all())
                if len(stages) >= 2:
                    stages[0].status = Stage.Status.COMPLETED
                    stages[0].save()
                    stages[1].status = Stage.Status.IN_PROGRESS
                    stages[1].save()

            # Application fee payment (N200,000 paid)
            Payment.objects.create(
                application=app,
                reference=f"PAY-{uuid.uuid4().hex[:12].upper()}",
                gateway=Payment.Gateway.PAYSTACK,
                status=Payment.Status.PAID,
                currency="NGN",
                symbol="₦",
                amount=Decimal("200000.00"),
                amount_ngn=Decimal("200000.00"),
            )

            # Standard Document uploads
            for doc_name, doc_kind in [
                ("International Passport", Document.Kind.PASSPORT),
                ("Academic Transcript & Certificate", Document.Kind.ACADEMIC),
                ("Curriculum Vitae (CV)", Document.Kind.CV),
                ("Academic Recommendation Letter", Document.Kind.OTHER),
            ]:
                Document.objects.create(
                    application=app,
                    kind=doc_kind,
                    name=doc_name,
                    status=Document.Status.VERIFIED if status == Application.Status.ADMITTED else Document.Status.PENDING,
                    file=ContentFile(SAMPLE_PDF_BYTES, name=f"{doc_kind}_{app.id}.pdf"),
                )

            # 4. Standard Agent Commissions:
            # Registration Commission: N30,000 for each registered student
            comm_reg = Commission.objects.create(
                agent=profile,
                application=app,
                kind=Commission.Kind.REGISTRATION,
                amount=reg_amount,
                amount_ngn=reg_amount,
                currency="NGN",
                earned_at=submitted_dt + timedelta(hours=2),
            )
            reg_comm_total += comm_reg.amount

            # Visa Commission: N50,000 once visa is approved/completed
            if visa_status == Application.VisaStatus.COMPLETED:
                comm_visa = Commission.objects.create(
                    agent=profile,
                    application=app,
                    kind=Commission.Kind.VISA,
                    amount=visa_amount,
                    amount_ngn=visa_amount,
                    currency="NGN",
                    earned_at=submitted_dt + timedelta(days=35),
                )
                visa_comm_total += comm_visa.amount

            # 5. Issued Letters: Admission Letters ONLY for admitted students
            if status == Application.Status.ADMITTED:
                Letter.objects.create(
                    application=app,
                    kind=Letter.Kind.ADMISSION,
                    title="Official Letter of Admission",
                    note="Official university letter of admission issued for academic intake.",
                    file=ContentFile(SAMPLE_PDF_BYTES, name=f"admission_letter_{app.id}.pdf"),
                    is_published=True,
                    issued_by=user,
                    issued_at=submitted_dt + timedelta(days=15),
                )

        # 6. Loan History (Ads funding history: 2 repaid loans + 1 declined loan)
        loans_data = [
            {
                "amount": Decimal("80000.00"),
                "purpose": "Meta & Instagram Lead Ads (Canada Fall Intake)",
                "status": Loan.Status.REPAID,
                "days_ago": 120,
                "repaid_days_ago": 60,
            },
            {
                "amount": Decimal("70000.00"),
                "purpose": "Google Search Ads Campaign (UK Masters Intake)",
                "status": Loan.Status.REPAID,
                "days_ago": 90,
                "repaid_days_ago": 30,
            },
            {
                "amount": Decimal("80000.00"),
                "purpose": "Radio Commercial Broadcast (Outside Ad Policy)",
                "status": Loan.Status.DECLINED,
                "days_ago": 150,
                "repaid_days_ago": None,
            },
        ]

        loan_repaid_total = Decimal("0.00")
        for ld in loans_data:
            Loan.objects.create(
                agent=profile,
                requested_amount=ld["amount"],
                approved_amount=ld["amount"] if ld["status"] == Loan.Status.REPAID else None,
                currency="NGN",
                purpose=ld["purpose"],
                ad_account_link="https://business.facebook.com/adsmanager",
                status=ld["status"],
                requested_at=now - timedelta(days=ld["days_ago"]),
                disbursed_at=(now - timedelta(days=ld["days_ago"] - 2)) if ld["status"] == Loan.Status.REPAID else None,
            )
            if ld["status"] == Loan.Status.REPAID and ld["repaid_days_ago"]:
                LoanRepayment.objects.create(
                    agent=profile,
                    amount=ld["amount"],
                    currency="NGN",
                    created_at=now - timedelta(days=ld["repaid_days_ago"]),
                )
                loan_repaid_total += ld["amount"]

        # 7. Withdrawals (2 completed payouts of N500,000 total)
        withdrawals_data = [
            (Decimal("300000.00"), 90),
            (Decimal("200000.00"), 35),
        ]
        total_withdrawn = Decimal("0.00")
        for w_amt, w_days_ago in withdrawals_data:
            Withdrawal.objects.create(
                agent=profile,
                amount_requested=w_amt,
                net_amount=w_amt,
                currency="NGN",
                status=Withdrawal.Status.PAID,
                paid_to=f"Zenith Bank · 2109876543 · {full_name}",
                created_at=now - timedelta(days=w_days_ago),
            )
            total_withdrawn += w_amt

        # 8. Student Drafts
        StudentDraft.objects.create(
            agent=profile,
            step=2,
            data={
                "fullName": "Olumuyiwa Babatunde Adeleke",
                "email": "olumuyiwa.draft@gmail.com",
                "phone": "+2348039988776",
                "country": "Nigeria",
                "destination": "Canada",
            },
        )
        StudentDraft.objects.create(
            agent=profile,
            step=1,
            data={
                "fullName": "Fatima Aliyu",
                "email": "fatima.draft@gmail.com",
                "phone": "+2348057766554",
                "country": "Nigeria",
                "destination": "Spain",
            },
        )

        # 9. Wallet Configuration:
        # Total Earned:
        #   - 48 Registrations @ N30,000 = N1,440,000.00
        #   - 28 Visas @ N50,000         = N1,400,000.00
        #   Total Earned                 = N2,840,000.00
        # Deductions:
        #   - Total Withdrawn: N500,000.00
        #   - Savings: N50,000.00
        #   - Loans Repaid: N150,000.00
        # Available Balance:
        #   N2,840,000 - N500,000 - N50,000 - N150,000 = N2,140,000.00 (Over 2 Million Naira)
        saved_balance = Decimal("50000.00")
        total_earned = reg_comm_total + visa_comm_total

        wallet, _ = Wallet.objects.get_or_create(agent=profile)
        wallet.currency = "NGN"
        wallet.registration_commission_total = reg_comm_total
        wallet.visa_commission_total = visa_comm_total
        wallet.total_earned = total_earned
        wallet.total_withdrawn = total_withdrawn
        wallet.saved_balance = saved_balance
        wallet.loan_repaid_total = loan_repaid_total
        wallet.loan_balance = Decimal("0.00")
        wallet.save()

        avail = wallet.available_balance

        self.stdout.write(self.style.SUCCESS(f"\n=========================================="))
        self.stdout.write(self.style.SUCCESS(f" Test Agent Successfully Configured!"))
        self.stdout.write(self.style.SUCCESS(f"=========================================="))
        self.stdout.write(f"Email:             {email}")
        self.stdout.write(f"Password:          {password}")
        self.stdout.write(f"Agent Name:        {full_name}")
        self.stdout.write(f"Agency Name:       {agency_name}")
        self.stdout.write(f"Partner Code:      {profile.partner_code}")
        self.stdout.write(f"Bank Account:      Zenith Bank - 2109876543 ({full_name})")
        self.stdout.write(f"------------------------------------------")
        self.stdout.write(f"Per-Student Rate:  NGN 30,000 at Registration + NGN 50,000 at Visa Approval")
        self.stdout.write(f"Registration Comm: NGN {reg_comm_total:,.2f}  (48 students x NGN 30,000)")
        self.stdout.write(f"Visa Comm:         NGN {visa_comm_total:,.2f}  (28 students x NGN 50,000)")
        self.stdout.write(f"Total Earned:      NGN {total_earned:,.2f}")
        self.stdout.write(f"Total Withdrawn:   NGN {total_withdrawn:,.2f}  (2 completed payouts)")
        self.stdout.write(f"Saved in Reserve:  NGN {saved_balance:,.2f}")
        self.stdout.write(f"Loans Repaid:      NGN {loan_repaid_total:,.2f}")
        self.stdout.write(f"Active Debt:       NGN {wallet.loan_balance:,.2f}")
        self.stdout.write(self.style.SUCCESS(f"Available Balance: NGN {avail:,.2f}  (> 2 Million Naira)"))
        self.stdout.write(f"------------------------------------------")
        self.stdout.write(f"Students:          48 Registered Nigerian Students")
        self.stdout.write(f"Issued Letters:    Admission Letters ONLY (for all admitted students)")
        self.stdout.write(f"Loan Records:      3 (2 Repaid, 1 Declined)")
        self.stdout.write(f"Withdrawal Runs:   2 Completed Payouts")
        self.stdout.write(self.style.SUCCESS(f"==========================================\n"))
