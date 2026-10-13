"""Seed a realistic test agent account with rich history.

Creates:
- A Nigerian partner agent account (Chukwuemeka Kingsley Okonkwo)
- 18 registered Nigerian students with completed payments and pipeline progression
- 14 issued official letters (Offer, Admission, Visa, Financial/Scholarship) with real PDF attachments
- Extensive Ads Funding loan history (4 fully repaid loans, 1 declined loan, 4 repayment records)
- Active withdrawal history (3 completed payouts of N1,050,000 total)
- Active savings reserve of N150,000
- Available wallet balance of over N2,430,000 (well over 2 million Naira)
- Zero active debt so the agent can freely request new loans or make withdrawals
"""

from datetime import timedelta
from decimal import Decimal
import os
import uuid

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.applications.models import (
    Application,
    Document,
    Letter,
    Stage,
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

import io
import pypdf

def _make_sample_pdf():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

SAMPLE_PDF_BYTES = _make_sample_pdf()


class Command(BaseCommand):
    help = "Seeds a test agent account with rich Nigerian history, loans, letters, and >2M balance."

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

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        full_name = options["name"].strip()
        phone = "+2348035678912"
        agency_name = "Okonkwo Global Education & Travel Consult"

        self.stdout.write(f"Setting up test agent account: {email}...")

        # 1. User Account
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "phone": phone,
                "role": User.Role.AGENT,
                "country": "Nigeria",
                "email_verified": True,
                "is_active": True,
            },
        )
        user.full_name = full_name
        user.phone = phone
        user.role = User.Role.AGENT
        user.country = "Nigeria"
        user.email_verified = True
        user.is_active = True
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
                "total_closed_sales": 16,
            },
        )
        profile.agency_name = agency_name
        profile.bank_name = "Zenith Bank"
        profile.account_number = "2109876543"
        profile.account_name = full_name
        profile.total_closed_sales = 16
        profile.save()

        # 3. Clean up previous seeded relations under this agent for idempotency
        Application.objects.filter(submitted_by_agent=profile).delete()
        Loan.objects.filter(agent=profile).delete()
        LoanRepayment.objects.filter(agent=profile).delete()
        Withdrawal.objects.filter(agent=profile).delete()
        Commission.objects.filter(agent=profile).delete()
        StudentDraft.objects.filter(agent=profile).delete()

        # 4. Origin & Destination Countries
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

        # 5. Create 18 Student Applicants
        students_data = [
            # 6 Admitted & Visa Completed (Verified)
            {
                "name": "Chioma Blessing Eze",
                "email": "chioma.eze.student@gmail.com",
                "phone": "+2348021122334",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (4.2/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.COMPLETED,
                "days_ago": 160,
                "dest_idx": 0,
            },
            {
                "name": "Babatunde Ayodele Adeleke",
                "email": "babatunde.adeleke.student@gmail.com",
                "phone": "+2348032233445",
                "qualification": "Master's Degree",
                "grade": "Distinction",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.COMPLETED,
                "days_ago": 145,
                "dest_idx": 1,
            },
            {
                "name": "Amina Zainab Usman",
                "email": "amina.usman.student@gmail.com",
                "phone": "+2348053344556",
                "qualification": "Bachelor's Degree",
                "grade": "First Class Honours (4.8/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.COMPLETED,
                "days_ago": 130,
                "dest_idx": 2,
            },
            {
                "name": "Emeka Victor Nnamdi",
                "email": "emeka.nnamdi.student@gmail.com",
                "phone": "+2348064455667",
                "qualification": "HND",
                "grade": "Upper Credit",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.COMPLETED,
                "days_ago": 115,
                "dest_idx": 3,
            },
            {
                "name": "Damilola Sarah Oladipo",
                "email": "damilola.oladipo.student@gmail.com",
                "phone": "+2348075566778",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (4.3/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.COMPLETED,
                "days_ago": 100,
                "dest_idx": 4,
            },
            {
                "name": "Ifeanyi Samuel Okorie",
                "email": "ifeanyi.okorie.student@gmail.com",
                "phone": "+2348086677889",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (4.1/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.COMPLETED,
                "days_ago": 90,
                "dest_idx": 0,
            },
            # 4 Admitted & Visa In Progress
            {
                "name": "Favour Temitope Ajayi",
                "email": "favour.ajayi.student@gmail.com",
                "phone": "+2348097788990",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (3.9/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.IN_PROGRESS,
                "days_ago": 75,
                "dest_idx": 1,
            },
            {
                "name": "Olumide Kazeem Sanusi",
                "email": "olumide.sanusi.student@gmail.com",
                "phone": "+2348108899001",
                "qualification": "SSCE / High School",
                "grade": "6 Credits (WAEC)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.IN_PROGRESS,
                "days_ago": 60,
                "dest_idx": 2,
            },
            {
                "name": "Ngozi Cynthia Onyekwere",
                "email": "ngozi.onyekwere.student@gmail.com",
                "phone": "+2348119900112",
                "qualification": "Master's Degree",
                "grade": "Merit",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.IN_PROGRESS,
                "days_ago": 52,
                "dest_idx": 3,
            },
            {
                "name": "Chidiebere Collins Umeh",
                "email": "chidiebere.umeh.student@gmail.com",
                "phone": "+2348120011223",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Lower (3.2/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.IN_PROGRESS,
                "days_ago": 45,
                "dest_idx": 4,
            },
            # 2 Admitted (Visa Not Started)
            {
                "name": "Aisha Maryam Bello",
                "email": "aisha.bello.student@gmail.com",
                "phone": "+2348131122334",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (4.4/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 35,
                "dest_idx": 0,
            },
            {
                "name": "Tobi Joshua Fashola",
                "email": "tobi.fashola.student@gmail.com",
                "phone": "+2348142233445",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (4.0/5.0)",
                "status": Application.Status.ADMITTED,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 28,
                "dest_idx": 1,
            },
            # 4 In Review
            {
                "name": "Somtochukwu David Madu",
                "email": "somto.madu.student@gmail.com",
                "phone": "+2348153344556",
                "qualification": "HND",
                "grade": "Upper Credit",
                "status": Application.Status.IN_REVIEW,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 20,
                "dest_idx": 2,
            },
            {
                "name": "Kehinde Paul Alabi",
                "email": "kehinde.alabi.student@gmail.com",
                "phone": "+2348164455667",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Lower (3.4/5.0)",
                "status": Application.Status.IN_REVIEW,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 16,
                "dest_idx": 3,
            },
            {
                "name": "Precious Nkechi Obi",
                "email": "precious.obi.student@gmail.com",
                "phone": "+2348175566778",
                "qualification": "SSCE / High School",
                "grade": "7 Credits (NECO)",
                "status": Application.Status.IN_REVIEW,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 12,
                "dest_idx": 4,
            },
            {
                "name": "Halima Fatima Danjuma",
                "email": "halima.danjuma.student@gmail.com",
                "phone": "+2348186677889",
                "qualification": "Bachelor's Degree",
                "grade": "First Class Honours (4.7/5.0)",
                "status": Application.Status.IN_REVIEW,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 8,
                "dest_idx": 0,
            },
            # 2 Submitted
            {
                "name": "Osasere Godstime Ighodaro",
                "email": "osasere.ighodaro.student@gmail.com",
                "phone": "+2348197788990",
                "qualification": "Bachelor's Degree",
                "grade": "Second Class Upper (3.8/5.0)",
                "status": Application.Status.SUBMITTED,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 5,
                "dest_idx": 1,
            },
            {
                "name": "Chiamaka Grace Nwosu",
                "email": "chiamaka.nwosu.student@gmail.com",
                "phone": "+2348208899001",
                "qualification": "OND",
                "grade": "Upper Credit",
                "status": Application.Status.SUBMITTED,
                "visa_status": Application.VisaStatus.NOT_STARTED,
                "days_ago": 2,
                "dest_idx": 2,
            },
        ]

        created_apps = []
        for s_idx, s in enumerate(students_data):
            applicant_user, _ = User.objects.get_or_create(
                email=s["email"],
                defaults={
                    "full_name": s["name"],
                    "phone": s["phone"],
                    "role": User.Role.APPLICANT,
                    "country": "Nigeria",
                    "email_verified": True,
                    "is_active": True,
                },
            )
            applicant_user.full_name = s["name"]
            applicant_user.set_password("StudentPass2026!")
            applicant_user.save()

            dest_choice = destinations[s["dest_idx"] % len(destinations)]
            inst_choice = institutions[s_idx % len(institutions)] if institutions else None

            submitted_dt = now - timedelta(days=s["days_ago"])
            is_admitted = s["status"] == Application.Status.ADMITTED

            app = Application.objects.create(
                applicant=applicant_user,
                submitted_by_agent=profile,
                full_name=s["name"],
                email=s["email"],
                phone=s["phone"],
                address="Plot 14 Victoria Island, Lagos, Nigeria",
                origin_country=origin_nigeria,
                destination_country=dest_choice,
                institution=inst_choice,
                qualification=s["qualification"],
                grade_gpa=s["grade"],
                year_graduated=2023,
                status=s["status"],
                visa_status=s["visa_status"],
                transferred_to_visa_support=(s["visa_status"] != Application.VisaStatus.NOT_STARTED),
                transferred_to_visa_support_at=(submitted_dt + timedelta(days=20)) if (s["visa_status"] != Application.VisaStatus.NOT_STARTED) else None,
                verification_status=(
                    Application.VerificationStatus.VERIFIED if is_admitted
                    else Application.VerificationStatus.IN_REVIEW if s["status"] == Application.Status.IN_REVIEW
                    else Application.VerificationStatus.UNVERIFIED
                ),
                personal_details_verified=is_admitted,
                academic_details_verified=is_admitted,
                submitted_at=submitted_dt,
            )

            # Link program
            if programs:
                prog_choice = programs[s_idx % len(programs)]
                app.programs.add(prog_choice)

            # Build default timeline stages
            app.build_default_stages(first_note="Application submitted and verified.")
            if is_admitted:
                app.stages.all().update(status=Stage.Status.COMPLETED)
            elif s["status"] == Application.Status.IN_REVIEW:
                stages = list(app.stages.all())
                if len(stages) >= 2:
                    stages[0].status = Stage.Status.COMPLETED
                    stages[0].save()
                    stages[1].status = Stage.Status.IN_PROGRESS
                    stages[1].save()

            # Create payment
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

            # Create supporting documents
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
                    status=Document.Status.VERIFIED if is_admitted else Document.Status.PENDING,
                    file=ContentFile(SAMPLE_PDF_BYTES, name=f"{doc_kind}_sample.pdf"),
                )

            created_apps.append((app, s, submitted_dt))

        # 6. Commissions Setup
        # Registration commission for all 18 paid students (N135,000 each) = N2,430,000
        # Visa commission for the 10 students with visa in progress or completed (N150,000 each) = N1,500,000
        reg_comm_total = Decimal("0.00")
        visa_comm_total = Decimal("0.00")

        for app, s, submitted_dt in created_apps:
            comm_reg = Commission.objects.create(
                agent=profile,
                application=app,
                kind=Commission.Kind.REGISTRATION,
                amount=Decimal("135000.00"),
                amount_ngn=Decimal("135000.00"),
                currency="NGN",
                earned_at=submitted_dt + timedelta(hours=2),
            )
            reg_comm_total += comm_reg.amount

            if s["visa_status"] in (Application.VisaStatus.IN_PROGRESS, Application.VisaStatus.COMPLETED):
                comm_visa = Commission.objects.create(
                    agent=profile,
                    application=app,
                    kind=Commission.Kind.VISA,
                    amount=Decimal("150000.00"),
                    amount_ngn=Decimal("150000.00"),
                    currency="NGN",
                    earned_at=submitted_dt + timedelta(days=25),
                )
                visa_comm_total += comm_visa.amount

        # 7. Issued Letters Setup (Admission letters only)
        letters_data = [
            (0, Letter.Kind.ADMISSION, "Official Letter of Admission", "Unconditional admission granted for Fall intake.", 140),
            (1, Letter.Kind.ADMISSION, "Official Letter of Admission", "Admission granted into postgraduate degree program.", 130),
            (2, Letter.Kind.ADMISSION, "Official Letter of Admission", "Official admission confirmation issued by the university admissions desk.", 115),
            (3, Letter.Kind.ADMISSION, "Official Letter of Admission", "Direct admission granted for academic session.", 100),
            (4, Letter.Kind.ADMISSION, "Official Letter of Admission", "Full admission letter and enrollment confirmation.", 85),
            (5, Letter.Kind.ADMISSION, "Official Letter of Admission", "Unconditional admission letter issued.", 75),
            (6, Letter.Kind.ADMISSION, "Official Letter of Admission", "Official admission decision and acceptance verification.", 65),
            (7, Letter.Kind.ADMISSION, "Official Letter of Admission", "University admission confirmed for student visa processing.", 55),
            (8, Letter.Kind.ADMISSION, "Official Letter of Admission", "Admission granted for selected study program.", 45),
            (9, Letter.Kind.ADMISSION, "Official Letter of Admission", "Official letter of admission issued to applicant.", 40),
            (10, Letter.Kind.ADMISSION, "Official Letter of Admission", "Admissions desk approval and official entry letter.", 30),
            (11, Letter.Kind.ADMISSION, "Official Letter of Admission", "Academic admission granted for international intake.", 25),
        ]

        for student_idx, l_kind, l_title, l_note, l_days_ago in letters_data:
            app, _, _ = created_apps[student_idx]
            Letter.objects.create(
                application=app,
                kind=l_kind,
                title=l_title,
                note=l_note,
                file=ContentFile(SAMPLE_PDF_BYTES, name=f"letter_{l_kind}_{student_idx}.pdf"),
                is_published=True,
                issued_by=user,
                issued_at=now - timedelta(days=l_days_ago),
            )

        # 8. Loan History (4 fully repaid loans, 1 declined loan, 4 repayments)
        loans_data = [
            {
                "amount": Decimal("80000.00"),
                "purpose": "Meta & Instagram Lead Ads (Canada Fall Intake)",
                "status": Loan.Status.REPAID,
                "days_ago": 180,
                "repaid_days_ago": 140,
            },
            {
                "amount": Decimal("75000.00"),
                "purpose": "Google Search Ads Campaign (UK Masters Intake)",
                "status": Loan.Status.REPAID,
                "days_ago": 130,
                "repaid_days_ago": 95,
            },
            {
                "amount": Decimal("80000.00"),
                "purpose": "TikTok Video Marketing & Study Abroad Leads",
                "status": Loan.Status.REPAID,
                "days_ago": 85,
                "repaid_days_ago": 55,
            },
            {
                "amount": Decimal("65000.00"),
                "purpose": "Lagos & Abuja Student Fair Social Media Sponsorship",
                "status": Loan.Status.REPAID,
                "days_ago": 45,
                "repaid_days_ago": 15,
            },
            {
                "amount": Decimal("80000.00"),
                "purpose": "Radio Broadcast Commercial Spot (Ikeja Station)",
                "status": Loan.Status.DECLINED,
                "days_ago": 210,
                "repaid_days_ago": None,
            },
        ]

        loan_repaid_total = Decimal("0.00")
        for ld in loans_data:
            loan = Loan.objects.create(
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

        # 9. Withdrawals History (3 completed payouts of N1,050,000 total)
        withdrawals_data = [
            (Decimal("400000.00"), 120),
            (Decimal("400000.00"), 70),
            (Decimal("250000.00"), 25),
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

        # 10. Student Drafts (In-progress drafts for portal demonstration)
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

        # 11. Wallet Configuration
        # Total earned: N2,430,000 + N1,500,000 = N3,930,000
        # Withdrawals: N1,050,000
        # Savings: N150,000
        # Repaid loans: N300,000
        # Active loan balance: 0.00
        # Available balance = 3,930,000 - 1,050,000 - 150,000 - 300,000 = N2,430,000.00
        saved_balance = Decimal("150000.00")
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
        self.stdout.write(f"Total Earned:      NGN {total_earned:,.2f}")
        self.stdout.write(f"Total Withdrawn:   NGN {total_withdrawn:,.2f}")
        self.stdout.write(f"Saved in Reserve:  NGN {saved_balance:,.2f}")
        self.stdout.write(f"Loans Repaid:      NGN {loan_repaid_total:,.2f}")
        self.stdout.write(f"Active Debt:       NGN {wallet.loan_balance:,.2f}")
        self.stdout.write(self.style.SUCCESS(f"Available Balance: NGN {avail:,.2f}  (> 2 Million Naira)"))
        self.stdout.write(f"------------------------------------------")
        self.stdout.write(f"Students:          18 Registered Nigerian Students")
        self.stdout.write(f"Issued Letters:    12 Official Admission Letters (Admission only)")
        self.stdout.write(f"Loan Records:      5 (4 Repaid, 1 Declined)")
        self.stdout.write(f"Withdrawal Runs:   3 Completed Payouts")
        self.stdout.write(self.style.SUCCESS(f"==========================================\n"))
