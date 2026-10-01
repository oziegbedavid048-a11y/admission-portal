"""Transactional email.

The design is deliberately plain: a line of sender text, the message, a link,
and a three-line footer. No banner, no coloured panels, no marketing furniture.
These are records of something that happened to someone's money or their
application, and they are read on a phone in ten seconds, so they are built to
be skimmed rather than admired. Plain HTML also survives Outlook and Gmail
clipping, which an elaborate table layout does not.

Sending happens on a daemon thread so an HTTP response is never held up by SMTP,
and a failure is logged rather than raised: an account is still created if the
mail server is briefly unreachable.
"""

import html
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape

logger = logging.getLogger(__name__)


def _send_mail_worker(subject, text_content, html_content, recipient_list):
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        if html_content:
            message.attach_alternative(html_content, "text/html")
        message.send(fail_silently=False)
        logger.info("Email sent: %r to %s", subject, recipient_list)
    except Exception as exc:
        logger.error("Email failed: %r to %s: %s", subject, recipient_list, exc)


def _send_mail_now(subject, text_content, html_content, recipient_list):
    """Send on this thread and say whether it worked.

    For the messages where "did it arrive" decides what happens next. The
    credentials email is the one that matters: the caller records that it was sent
    and throws the password away, so it has to know rather than assume.
    """
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        if html_content:
            message.attach_alternative(html_content, "text/html")
        message.send(fail_silently=False)
        logger.info("Email sent: %r to %s", subject, recipient_list)
        return True
    except Exception as exc:
        logger.error("Email failed: %r to %s: %s", subject, recipient_list, exc)
        return False


def send_async_email(subject, text_content, html_content, recipient_list, wait=False):
    """Queue a message, or send it now and report the outcome.

    The default is a daemon thread, so an HTTP response is never held up by SMTP.
    That is right for a status update, and wrong for anything whose success the
    caller records: a daemon thread cannot raise into the caller, and it dies
    silently if the worker process exits first, which is easy to arrange on a
    host that recycles workers between requests. Both of those looked like a sent
    email and were not one.

    `wait=True` sends on this thread and returns True or False.
    """
    recipients = [address for address in dict.fromkeys(recipient_list) if address]
    if not recipients:
        return False
    if wait:
        return _send_mail_now(subject, text_content, html_content, recipients)
    threading.Thread(
        target=_send_mail_worker,
        args=(subject, text_content, html_content, recipients),
        daemon=True,
    ).start()
    return None


def _url(path="/"):
    base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}{path}"


def _first_name(full_name, fallback="there"):
    """The first name, written properly even if it was typed in capitals."""
    first = (full_name or "").strip().split(" ")[0]
    if first and (first.isupper() or first.islower()):
        first = first.capitalize()
    return first or fallback


def _naira(amount):
    return f"₦{amount:,.0f}"


# ── Rendering ────────────────────────────────────────────────────────

BODY = "margin:0;padding:24px;background:#ffffff;color:#111827;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;"
WRAP = "max-width:560px;margin:0 auto;"
P = "margin:0 0 16px;color:#111827;"
LINK = "color:#065f46;"


def _render(greeting, paragraphs, facts=None, action=None, items=None, items_intro=None):
    """One message: a greeting, some sentences, an optional list, one link.

    `facts` is a list of (label, value) pairs rendered as plain rows. `action`
    is a (text, url) pair rendered as a link rather than a button, because a
    link is unambiguous in every client and needs no styling to work.

    Everything except `paragraphs` is plain text and is escaped here: names,
    course names and file names are typed by the people the email is about,
    and must never turn into links or markup in a message sent as Gabstep.
    `paragraphs` may carry deliberate markup, so callers escape any value they
    put into one.
    """
    greeting = escape(greeting)
    facts = [(escape(label), escape(value)) for label, value in (facts or [])]
    items = [(escape(title), escape(text)) for title, text in (items or [])]
    items_intro = escape(items_intro) if items_intro else items_intro
    if action:
        action = (escape(action[0]), escape(action[1]))
    parts = [f'<p style="{P}">{greeting}</p>']
    parts += [f'<p style="{P}">{text}</p>' for text in paragraphs]

    if facts:
        rows = "".join(
            f'<tr>'
            f'<td style="padding:4px 16px 4px 0;color:#6b7280;white-space:nowrap;">{label}</td>'
            f'<td style="padding:4px 0;color:#111827;font-weight:600;">{value}</td>'
            f"</tr>"
            for label, value in facts
        )
        parts.append(
            f'<table cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:0 0 16px;border-collapse:collapse;font-size:15px;">{rows}</table>'
        )

    if items:
        if items_intro:
            parts.append(f'<p style="{P}">{items_intro}</p>')
        rows = "".join(
            f'<li style="margin:0 0 10px;"><strong>{title}</strong><br>'
            f'<span style="color:#374151;">{text}</span></li>'
            for title, text in items
        )
        parts.append(f'<ul style="margin:0 0 16px;padding-left:20px;color:#111827;">{rows}</ul>')

    if action:
        text, url = action
        parts.append(
            f'<p style="{P}"><a href="{url}" style="{LINK}" target="_blank" '
            f'rel="noopener">{text}</a></p>'
        )

    body = "".join(parts)
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body style="{BODY}"><div style="{WRAP}">'
        f"{body}"
        f"{_footer_html()}"
        f"</div></body></html>"
    )


# ── Footer ───────────────────────────────────────────────────────────
#
# Three short lines under a hairline: who sent it, where to go, and why the
# reader got it. Nothing to unsubscribe from: every message here is about the
# reader's own account or file.

FOOTER_RULE = "margin:32px 0 16px;border:0;border-top:1px solid #e5e7eb;"
FOOTER_LINE = "margin:0 0 4px;color:#6b7280;font-size:12px;line-height:1.5;"
FOOTER_LINK = "color:#065f46;text-decoration:none;"


def _site():
    """The site address and the bare host to print for it."""
    url = _url("/")
    host = url.split("://", 1)[-1].rstrip("/")
    return url, host


def _footer_html():
    url, host = _site()
    support = getattr(settings, "SUPPORT_EMAIL", "support@gabstep.com")
    year = timezone.now().year
    return (
        f'<hr style="{FOOTER_RULE}">'
        f'<p style="{FOOTER_LINE}"><strong style="color:#111827;">Gabstep</strong> '
        f"&middot; Study abroad applications</p>"
        f'<p style="{FOOTER_LINE}">'
        f'<a href="{url}" style="{FOOTER_LINK}" target="_blank" rel="noopener">{host}</a>'
        f' &middot; <a href="mailto:{support}" style="{FOOTER_LINK}">{support}</a></p>'
        f'<p style="{FOOTER_LINE}">You received this email about your Gabstep account. '
        f"&copy; {year} Gabstep</p>"
    )


def _footer_plain():
    url, _host = _site()
    support = getattr(settings, "SUPPORT_EMAIL", "support@gabstep.com")
    year = timezone.now().year
    return "\n".join([
        "--",
        "Gabstep · Study abroad applications",
        f"{url} · {support}",
        f"You received this email about your Gabstep account. © {year} Gabstep",
    ])


def _plain(greeting, paragraphs, facts=None, action=None, items=None, items_intro=None):
    from django.utils.html import strip_tags

    lines = [greeting, ""]
    lines += [line for text in paragraphs for line in (html.unescape(strip_tags(text)), "")]
    if facts:
        lines += [f"{label}: {value}" for label, value in facts]
        lines.append("")
    if items:
        if items_intro:
            lines += [items_intro, ""]
        lines += [f"- {title}: {text}" for title, text in items]
        lines.append("")
    if action:
        lines += [f"{action[0]}: {action[1]}", ""]
    lines.append(_footer_plain())
    return "\n".join(lines)


def _send(subject, recipients, greeting, paragraphs, facts=None, action=None, wait=False, items=None, items_intro=None):
    return send_async_email(
        subject,
        _plain(greeting, paragraphs, facts, action, items, items_intro),
        _render(greeting, paragraphs, facts, action, items, items_intro),
        recipients,
        wait=wait,
    )


# ── Accounts ─────────────────────────────────────────────────────────


def send_applicant_welcome_email(user, password=None, wait=False):
    """The one email an applicant gets when their account is made.

    `wait=True` sends on this thread and returns whether it worked. The caller
    that clears the stored password uses that, because a password thrown away
    after a send that silently failed cannot be recovered by anybody.
    """
    facts = [("Email", user.email)]
    if password:
        facts.append(("Password", password))

    paragraphs = [
        "Your Gabstep account is ready. You can sign in to follow your application, "
        "upload documents and download any letters we issue."
    ]
    if password:
        paragraphs.append("You can change this password from your profile at any time.")

    return _send(
        subject="Your Gabstep account",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name)},",
        paragraphs=paragraphs,
        facts=facts,
        action=("Sign in", _url("/portal")),
        wait=wait,
    )


def send_agent_welcome_email(user, agent_profile=None):
    facts = [("Email", user.email)]
    if agent_profile:
        facts += [
            ("Bank", agent_profile.bank_name),
            ("Account", f"{agent_profile.account_number} ({agent_profile.account_name})"),
        ]

    _send(
        subject="Your Gabstep partner account",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your partner account is active. You can register students, follow their "
            "applications and withdraw your commission from the portal.",
            "Commission is paid to the account below. Update it from your profile if "
            "anything is wrong.",
        ],
        facts=facts,
        action=("Open the partner portal", _url("/agent/login")),
    )


def send_sales_manager_welcome_email(user, profile, password=None):
    """Sent when the admissions desk creates a sales manager account.

    They do not sign themselves up, so without this they would have no way of
    knowing the account exists or what their agent code is.
    """
    facts = [("Email", user.email)]
    if password:
        facts.append(("Password", password))
    facts.append(("Agent code", profile.agent_code))

    paragraphs = [
        "Your Gabstep sales manager account is ready.",
        f"Give your agent code, {profile.agent_code}, to the agents who report to you. "
        "They enter it when they register, and from then on you can see them and every "
        "student they file.",
    ]
    if password:
        paragraphs.append("You can change this password from your profile at any time.")

    _send(
        subject="Your Gabstep sales manager account",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=paragraphs,
        facts=facts,
        action=("Sign in", _url("/sales-manager/login")),
    )


# ── Applications ─────────────────────────────────────────────────────


NEXT_STEP_BY_STAGE = {
    "Submitted & payment confirmed": "Our admissions desk reviews your details and documents.",
    "Document verification": "We are checking your documents and will tell you if anything needs replacing.",
    "Institution review": "The university is reviewing your file. Decisions usually take two to four weeks.",
    "Offer letter decision": "Your letter appears in your dashboard as soon as the university issues it.",
    "Visa guidance & enrolment": "Our visa desk guides you through your study permit and enrolment.",
}


def _file_facts(application, *, include_student=False):
    """The facts every update about a file carries, in the same order each time."""
    stages = list(application.stages.all())
    current = application.current_stage
    position = (stages.index(current) + 1) if current in stages else None
    courses = ", ".join(program.name for program in application.programs.all()) or application.custom_course_name

    facts = []
    if include_student:
        facts.append(("Student", application.full_name))
    facts.append(("Reference", application.reference))
    facts.append(("University", application.institution.name if application.institution else "To be confirmed"))
    if courses:
        facts.append(("Course", courses))
    facts.append(("Destination", application.destination_country.name))
    if current:
        facts.append(("Stage", f"{current.name} (step {position} of {len(stages)})" if position else current.name))
    facts.append(("Status", application.get_status_display()))
    return facts, current


def send_application_status_update_email(application, notification_text, subject_override=None):
    """Tell whoever owns this file that something moved, with the full picture.

    A file registered through the partner portal belongs to the agent, not the
    student: the agent collected the documents, pays the fee and hands over the
    letters. So the update goes to the agent alone, and the student is never
    written to. A file the applicant opened themselves goes to the applicant.

    Every update says what changed, where the file stands, and what happens
    next, so the email makes sense without opening the dashboard.
    """
    agent = application.submitted_by_agent
    to_agent = bool(agent and agent.user and agent.user.email)
    if not to_agent and not application.email:
        return

    from django.utils.html import escape

    notification_text = escape(notification_text)
    facts, current = _file_facts(application, include_student=to_agent)
    next_step = NEXT_STEP_BY_STAGE.get(current.name) if current else None
    items = [("What happens next", next_step)] if next_step else None

    if to_agent:
        _send(
            subject=subject_override or f"{application.full_name}: update on {application.reference}",
            recipients=[agent.user.email],
            greeting=f"Hello {_first_name(agent.user.full_name, 'there')},",
            paragraphs=[
                f"There is a new update on the application you filed for <strong>{escape(application.full_name)}</strong>.",
                f"<strong>{notification_text}</strong>",
            ],
            facts=facts,
            items=items,
            action=("Open the student's file", _url("/agent/students")),
        )
        return

    _send(
        subject=subject_override or f"Update on your application {application.reference}",
        recipients=[application.email],
        greeting=f"Hello {_first_name(application.full_name, 'there')},",
        paragraphs=[
            "There is a new update on your Gabstep application.",
            f"<strong>{notification_text}</strong>",
        ],
        facts=facts,
        items=items,
        action=("View your application", _url("/portal")),
    )
    return


LETTER_HEADLINES = {
    "offer": "you have received an offer of admission",
    "admission": "you have been admitted",
    "acceptance": "your place has been confirmed",
    "visa": "your visa letter is ready",
    "financial": "your financial letter is ready",
}


def send_letter_issued_email(letter):
    """A letter was issued. Offers and admissions are written as the good news they are."""
    from django.utils import timezone

    application = letter.application
    agent = application.submitted_by_agent
    to_agent = bool(agent and agent.user and agent.user.email)
    if not to_agent and not application.email:
        return None

    school = application.institution.name if application.institution else "The university"
    courses = ", ".join(program.name for program in application.programs.all()) or application.custom_course_name
    celebrating = letter.kind in ("offer", "admission", "acceptance")
    headline = LETTER_HEADLINES.get(letter.kind, "a new letter is ready")
    issued = timezone.localtime(letter.issued_at).strftime("%d %B %Y") if letter.issued_at else ""

    facts = []
    if to_agent:
        facts.append(("Student", application.full_name))
    facts += [("Letter", letter.title), ("University", school)]
    if courses:
        facts.append(("Course", courses))
    facts += [("Destination", application.destination_country.name), ("Reference", application.reference)]
    if issued:
        facts.append(("Issued", issued))

    steps = [("Read and download the letter", "It is in the Letters section of the dashboard, ready to view or save.")]
    if celebrating:
        steps.append(("Send it to our visa desk", "Press Send to visa support on the letter, and a visa advisor takes it from there."))
        deposit = getattr(application.institution, "deposit_note", "") if application.institution else ""
        if deposit:
            steps.append(("Tuition deposit", deposit))
    steps.append(("Questions", "Our team answers from the Support page in the dashboard."))

    if to_agent:
        subject = f"{application.full_name}: {letter.title} from {school}"
        greeting = f"Hello {_first_name(agent.user.full_name, 'there')},"
        opening = (
            f"Good news: {escape(school)} has issued a {escape(letter.title.lower())} for "
            f"<strong>{escape(application.full_name)}</strong>."
            if celebrating
            else f"A new letter has been issued for <strong>{escape(application.full_name)}</strong>."
        )
        recipients, link = [agent.user.email], ("Open Letters", _url("/agent/letters"))
        steps = [
            ("Preview and download", "The letter is on your Letters page in the partner portal."),
        ]
        if celebrating:
            steps.append((
                "Send to visa support",
                "Press Send to visa support on the letter. Once our visa desk confirms the visa "
                "support is done, ₦50,000 is added to your wallet.",
            ))
        steps.append(("Questions", "Our team answers from the Support page in the portal."))
    else:
        first = _first_name(application.full_name, "there")
        subject = f"Congratulations, {first}: {headline}" if celebrating else f"{letter.title} is ready"
        greeting = f"Congratulations, {first}!" if celebrating else f"Hello {first},"
        opening = (
            f"{escape(school)} has offered you a place"
            + (f" on <strong>{escape(courses)}</strong>" if courses else "")
            + ". Your letter is now in your dashboard."
            if letter.kind == "offer"
            else f"Your {escape(letter.title.lower())} from {escape(school)} is now in your dashboard."
        )
        recipients, link = [application.email], ("View your letter", _url("/portal/letters"))

    return _send(
        subject=subject,
        recipients=recipients,
        greeting=greeting,
        paragraphs=[opening],
        facts=facts,
        items_intro="Your next steps:",
        items=steps,
        action=link,
    )


# ── Ads funding ───────────────────────────────────────────────────────


def send_loan_approved_email(loan):
    user = loan.agent.user
    _send(
        subject=f"Ads funding approved: {_naira(loan.approved_amount)}",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your ads funding request has been approved and sent to your registered "
            "bank account.",
            "Repayment is taken automatically at 10% of each commission withdrawal "
            "until the balance clears. There is no interest.",
        ],
        facts=[
            ("Reference", loan.reference),
            ("Amount", _naira(loan.approved_amount)),
            ("Platform", loan.purpose),
        ],
        action=("View your funding", _url("/agent/loans")),
    )


def send_loan_declined_email(loan):
    user = loan.agent.user
    _send(
        subject="Ads funding request declined",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "We could not approve this ads funding request. This is usually because "
            "the campaign link could not be reviewed, or an earlier balance is still "
            "outstanding.",
            "Reply to this email if you would like us to look at it again.",
        ],
        facts=[
            ("Reference", loan.reference),
            ("Amount requested", _naira(loan.requested_amount)),
            ("Platform", loan.purpose),
        ],
        action=("Request funding again", _url("/agent/loans")),
    )


# ── Payouts ──────────────────────────────────────────────────────────


def send_agent_payout_sent_email(withdrawal):
    agent = withdrawal.agent
    user = agent.user
    facts = [
        ("Reference", withdrawal.reference),
        ("Requested", _naira(withdrawal.amount_requested)),
    ]
    if withdrawal.loan_deduction:
        facts.append(("Ads funding repaid", _naira(withdrawal.loan_deduction)))
    facts += [
        ("Sent to you", _naira(withdrawal.net_amount)),
        ("Account", f"{agent.bank_name} {agent.account_number}"),
    ]

    _send(
        subject=f"Payout sent: {_naira(withdrawal.net_amount)}",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your withdrawal has been sent to your bank. It usually clears the same "
            "working day."
        ],
        facts=facts,
        action=("View your wallet", _url("/agent/wallet")),
    )


def send_agent_payout_failed_email(withdrawal):
    user = withdrawal.agent.user
    _send(
        subject="Payout could not be sent",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your withdrawal could not be sent, so the full amount has been returned "
            "to your available balance. Nothing has been lost.",
            "Check the payout account on your profile, then request it again.",
        ],
        facts=[
            ("Reference", withdrawal.reference),
            ("Amount returned", _naira(withdrawal.amount_requested)),
        ],
        action=("Check your payout account", _url("/agent/profile")),
    )


def send_manager_payout_sent_email(withdrawal):
    manager = withdrawal.supervisor
    user = manager.user
    _send(
        subject=f"Payout sent: {_naira(withdrawal.amount)}",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your withdrawal has been sent to your bank. It usually clears the same "
            "working day."
        ],
        facts=[
            ("Reference", withdrawal.reference),
            ("Amount", _naira(withdrawal.amount)),
            ("Account", f"{manager.bank_name} {manager.account_number}"),
        ],
        action=("View your earnings", _url("/sales-manager/earnings")),
    )


def send_manager_payout_failed_email(withdrawal):
    user = withdrawal.supervisor.user
    _send(
        subject="Payout could not be sent",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your withdrawal could not be sent, so the full amount has been returned "
            "to your available balance. Nothing has been lost.",
            "Check the payout account on your profile, then request it again.",
        ],
        facts=[
            ("Reference", withdrawal.reference),
            ("Amount returned", _naira(withdrawal.amount)),
        ],
        action=("Check your payout account", _url("/sales-manager/profile")),
    )


# ── Support ──────────────────────────────────────────────────────────


def send_support_ticket_email(ticket):
    """Deliver a Support page message to the support inbox.

    Reply-to is the sender, so answering from the inbox reaches them directly.
    Everything they typed is escaped: it is their text, shown as text, never as
    markup. Sent on this thread and returns whether it went, because the ticket
    records that and the page tells the sender.
    """
    from django.utils.html import escape

    user = ticket.user
    role = user.get_role_display()
    facts = [
        ("Reference", ticket.reference),
        ("From", f"{user.full_name or user.email} ({role})"),
        ("Email", user.email),
        ("Topic", ticket.get_topic_display()),
    ]
    if user.phone:
        facts.append(("Phone", user.phone))

    paragraphs = [escape(ticket.message).replace("\n", "<br>")]
    plain_paragraphs = [ticket.message]
    if ticket.attachment:
        paragraphs.append("An attachment is on the ticket in the admin.")
        plain_paragraphs.append("An attachment is on the ticket in the admin.")

    admin_link = (
        "Open in the admin",
        f"{getattr(settings, 'BACKEND_URL', '').rstrip('/')}/admin/accounts/supportticket/{ticket.pk}/change/",
    ) if getattr(settings, "BACKEND_URL", "") else None

    subject = f"[{ticket.reference}] {ticket.subject}"
    recipients = [getattr(settings, "SUPPORT_EMAIL", "support@gabstep.com")]
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=_plain("New support message", plain_paragraphs, facts, admin_link),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=[user.email],
        )
        message.attach_alternative(
            _render("New support message", paragraphs, facts, admin_link), "text/html"
        )
        message.send(fail_silently=False)
        logger.info("Support ticket %s emailed to %s", ticket.reference, recipients)
        return True
    except Exception as exc:
        logger.error("Support ticket %s could not be emailed: %s", ticket.reference, exc)
        return False


# ── Password reset ───────────────────────────────────────────────────


def send_password_reset_email(user, link, minutes):
    """The reset link. Sent to the account's own address and nowhere else."""
    return _send(
        subject="Reset your Gabstep password",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name)},",
        paragraphs=[
            "We received a request to reset the password for your Gabstep account.",
            f"The link below works once and expires in {minutes} minutes. If you did "
            "not ask for this, ignore this email and your password stays the same.",
        ],
        action=("Choose a new password", link),
    )


def send_password_changed_email(user):
    """Confirmation after a reset, so an unexpected change does not go unnoticed."""
    return _send(
        subject="Your Gabstep password was changed",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name)},",
        paragraphs=[
            "The password for your Gabstep account was just changed, and every "
            "device that was signed in has been signed out.",
            "If this was not you, reset your password straight away and contact "
            "support@gabstep.com.",
        ],
        action=("Reset password", _url("/forgot-password")),
    )


# ── Email verification and welcome ───────────────────────────────────


def send_verification_email(user, link, hours):
    """Confirm the address someone signed up with. Nothing else is in it."""
    return _send(
        subject="Confirm your email address",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name)},",
        paragraphs=[
            "Thank you for creating a Gabstep account. Please confirm this is your "
            "email address to activate it.",
            f"The link expires in {hours} hours. If you did not create an account, "
            "you can ignore this email.",
        ],
        action=("Confirm my email address", link),
        wait=True,
    )


APPLICANT_WELCOME = [
    ("Browse courses", "Choose a country, then a university, and compare courses with their tuition, duration and start dates."),
    ("Apply in minutes", "Apply to the course you want from your dashboard and upload your passport, transcripts and CV."),
    ("Pay securely", "Pay the application fee in your own currency."),
    ("Track every stage", "Follow your application from review to admission and visa, with an email at each step."),
    ("Receive your letters", "Your offer and admission letters appear in your dashboard as soon as they are issued."),
    ("Get help", "Our admissions team answers from the Support page in your dashboard."),
]

AGENT_WELCOME = [
    ("Register students", "File applications on behalf of your students and upload their documents in one place."),
    ("Browse courses", "Search every partner university by country, with tuition, duration and start dates."),
    ("Track progress", "Follow each student from submission to admission and visa. Updates come to you, not the student."),
    ("Earn commission", "You are paid when a student's fee is settled, and again when their visa is confirmed."),
    ("Ads funding", "Request interest-free funding for advertising, repaid from your earnings."),
    ("Withdraw earnings", "Send your balance to your bank account whenever you like."),
]


def send_welcome_email(user):
    """Sent once, when someone confirms their address: what the platform does for them."""
    if user.role == user.Role.AGENT:
        paragraphs = [
            "Your email is confirmed and your Gabstep partner account is active. "
            "Gabstep connects you with partner universities abroad and rewards you "
            "for every student you place.",
            "Here is what you can do from your partner portal:",
        ]
        items, action = AGENT_WELCOME, ("Open your partner portal", _url("/agent"))
        subject = "Welcome to the Gabstep partner network"
    else:
        paragraphs = [
            "Your email is confirmed and your Gabstep account is ready. Gabstep helps "
            "you find the right university abroad, apply with confidence and follow "
            "every step through to your visa.",
            "Here is what you can do from your dashboard:",
        ]
        items, action = APPLICANT_WELCOME, ("Go to your dashboard", _url("/portal"))
        subject = "Welcome to Gabstep"

    return _send(
        subject=subject,
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name)},",
        paragraphs=paragraphs + [],
        items=items,
        action=action,
    )



def send_support_reply_email(reply):
    """The desk's answer to a support message. Returns whether it was sent.

    Reply-to is the support inbox, so a person answering back reaches the desk.
    """
    from django.utils.html import escape

    ticket = reply.ticket
    user = ticket.user
    paragraphs = [escape(reply.body).replace("\n", "<br>")]
    try:
        message = EmailMultiAlternatives(
            subject=f"Re: [{ticket.reference}] {ticket.subject}",
            body=_plain(
                f"Hello {_first_name(user.full_name)},",
                [reply.body, f"Your message: {ticket.message}"],
                action=("View it in your dashboard", _support_url(user)),
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[getattr(settings, "SUPPORT_EMAIL", "support@gabstep.com")],
        )
        message.attach_alternative(
            _render(
                f"Hello {_first_name(user.full_name)},",
                paragraphs + [f'<span style="color:#6b7280;">Your message: {escape(ticket.message)}</span>'],
                action=("View it in your dashboard", _support_url(user)),
            ),
            "text/html",
        )
        message.send(fail_silently=False)
        logger.info("Support reply for %s emailed to %s", ticket.reference, user.email)
        return True
    except Exception as exc:
        logger.error("Support reply for %s could not be emailed: %s", ticket.reference, exc)
        return False


def _support_url(user):
    if user.role == user.Role.AGENT:
        return _url("/agent/support")
    if user.role == user.Role.SUPERVISOR:
        return _url("/sales-manager/support")
    return _url("/portal/support")


# ── Application received ─────────────────────────────────────────────


def send_application_received_email(application):
    """Confirms a new application to the applicant who submitted it.

    Only for applications people file themselves: a student an agent files is
    never written to, and the agent already knows what they submitted.
    """
    if application.submitted_by_agent_id or not application.email:
        return None

    institution = application.institution
    courses = ", ".join(program.name for program in application.programs.all())
    fee_due = not application.is_custom_course and institution is not None and not institution.is_fee_free

    facts = [("Reference", application.reference)]
    if application.is_custom_course:
        facts.append(("Course requested", application.custom_course_name or "To be confirmed"))
    else:
        facts.append(("University", institution.name if institution else "To be confirmed"))
        if courses:
            facts.append(("Course", courses))
    facts.append(("Destination", application.destination_country.name))

    if application.is_custom_course:
        next_steps = [
            ("Course matching", "Our admissions team will contact you to match your course with a partner university."),
            ("Document review", "We check the documents you uploaded and tell you if anything needs replacing."),
            ("Updates", "You receive an email at every stage, and you can follow everything from your dashboard."),
        ]
    else:
        next_steps = []
        if fee_due:
            next_steps.append(
                ("Application fee", "If you have not paid yet, pay it from your dashboard. Your file goes for review once it is paid.")
            )
        next_steps += [
            ("Document review", "Our admissions desk checks your details and documents."),
            ("University review", "Your file is sent to the university for an admission decision."),
            ("Offer letter", "Your letter appears in your dashboard as soon as it is issued."),
            ("Visa support", "Once admitted, our visa desk guides you through your study permit."),
        ]

    return _send(
        subject=f"Application received: {application.reference}",
        recipients=[application.email],
        greeting=f"Hello {_first_name(application.full_name)},",
        paragraphs=[
            "Thank you for applying through Gabstep. We have received your application "
            "and it is now with our admissions team.",
        ],
        items_intro="Here is what happens next:",
        items=next_steps,
        facts=facts,
        action=("Track your application", _url("/portal")),
    )



def send_document_rejected_email(document):
    """Tell the owner exactly which document was not accepted, why, and how to fix it."""
    from django.utils.html import escape

    application = document.application
    agent = application.submitted_by_agent
    to_agent = bool(agent and agent.user and agent.user.email)
    if not to_agent and not application.email:
        return None

    facts = []
    if to_agent:
        facts.append(("Student", application.full_name))
    facts += [("Document", document.name)]
    if document.original_filename:
        facts.append(("File", document.original_filename))
    facts += [
        ("Reference", application.reference),
        ("University", application.institution.name if application.institution else "To be confirmed"),
    ]

    where = "the student's file in your partner portal" if to_agent else "Application in your dashboard"
    steps = [
        ("Open the file", f"Go to {where} and find {document.name} under Documents."),
        ("Upload a replacement", "Press Upload a replacement and choose a clear, complete copy (PDF or photo, up to 10MB)."),
        ("We review it again", "The new copy goes straight back to our admissions desk. We email you once it is checked."),
    ]
    reason = escape(document.review_note or "It could not be accepted as uploaded.").replace("\n", "<br>")

    if to_agent:
        greeting = f"Hello {_first_name(agent.user.full_name, 'there')},"
        opening = f"We reviewed the {escape(document.name)} uploaded for <strong>{escape(application.full_name)}</strong> and could not accept it."
        recipients, link = [agent.user.email], ("Open the student's file", _url("/agent/students"))
    else:
        greeting = f"Hello {_first_name(application.full_name, 'there')},"
        opening = f"We reviewed your {escape(document.name)} and could not accept it yet."
        recipients, link = [application.email], ("Upload a replacement", _url("/portal/details"))

    return _send(
        subject=f"Action needed: please replace your {document.name}",
        recipients=recipients,
        greeting=greeting,
        paragraphs=[opening, f"<strong>Reason from our admissions desk:</strong><br>{reason}"],
        facts=facts,
        items_intro="How to fix it:",
        items=steps,
        action=link,
    )



def send_transfer_rejected_email(payment):
    """Tell whoever sent a transfer receipt why it could not be confirmed."""
    from django.utils.html import escape

    application = payment.application
    agent = application.submitted_by_agent
    to_agent = bool(agent and agent.user and agent.user.email)
    if not to_agent and not application.email:
        return None

    facts = []
    if to_agent:
        facts.append(("Student", application.full_name))
    facts += [
        ("Amount", payment.display_total),
        ("Payment reference", payment.reference),
        ("Application", application.reference),
    ]
    reason = escape(payment.review_note or "The transfer could not be matched to our account.").replace("\n", "<br>")
    steps = [
        ("Check the transfer", "Make sure the full amount was sent to the Gabstep company account shown on the payment screen."),
        ("Send the receipt again", "Open the student's payment and upload a clear receipt, or pay with Paystack instead."),
        ("We confirm it", "We check new receipts quickly and email you once the payment is confirmed."),
    ]
    if to_agent:
        greeting = f"Hello {_first_name(agent.user.full_name, 'there')},"
        opening = f"We could not confirm the bank transfer for <strong>{escape(application.full_name)}</strong>."
        recipients, link = [agent.user.email], ("Open your students", _url("/agent/students"))
    else:
        greeting = f"Hello {_first_name(application.full_name, 'there')},"
        opening = "We could not confirm your bank transfer for the application fee."
        recipients, link = [application.email], ("Open your dashboard", _url("/portal"))

    return _send(
        subject=f"Payment not confirmed for {application.reference}",
        recipients=recipients,
        greeting=greeting,
        paragraphs=[opening, f"<strong>Reason:</strong><br>{reason}"],
        facts=facts,
        items_intro="What to do next:",
        items=steps,
        action=link,
    )



# ── Agent: registrations, documents, commission ─────────────────────


def send_agent_student_registered_email(application):
    """Confirms to the agent that a student was registered, with what comes next."""
    agent = application.submitted_by_agent
    if agent is None or not agent.user.email:
        return None

    from django.utils.html import escape

    institution = application.institution
    courses = ", ".join(program.name for program in application.programs.all())
    fee_due = not application.is_custom_course and institution is not None and not institution.is_fee_free
    documents = list(application.documents.all())

    facts = [
        ("Student", application.full_name),
        ("Reference", application.reference),
        ("From", application.origin_country.name if application.origin_country else ""),
        ("To", application.destination_country.name if application.destination_country else ""),
    ]
    if application.is_custom_course:
        facts.append(("Course requested", application.custom_course_name or "To be confirmed"))
    else:
        facts.append(("University", institution.name if institution else "To be confirmed"))
        if courses:
            facts.append(("Course", courses))
    facts.append(("Documents", f"{len(documents)} uploaded" if documents else "None yet"))

    steps = []
    if fee_due:
        steps.append((
            "Pay the application fee",
            "Pay from the student's file in Students. Your first ₦30,000 is added to your wallet "
            "as soon as the payment is confirmed.",
        ))
    steps += [
        ("Document review", "Our admissions desk checks every document. You are emailed if one needs replacing, "
                            "and again once they are all verified."),
        ("Admission", "The file goes to the university. Every letter issued appears on your Letters page."),
        ("Visa support", "Send the letter to visa support. ₦50,000 is added once our visa desk confirms it is done."),
    ]

    return _send(
        subject=f"Student registered: {application.full_name} ({application.reference})",
        recipients=[agent.user.email],
        greeting=f"Hello {_first_name(agent.user.full_name, 'there')},",
        paragraphs=[
            f"You have registered <strong>{escape(application.full_name)}</strong>. "
            "The application is saved and linked to your partner account.",
        ],
        facts=facts,
        items_intro="What happens next:",
        items=steps,
        action=("Open your students", _url("/agent/students")),
    )


def send_documents_verified_email(application):
    """Every document on the file is verified. One email for the whole set."""
    from django.utils.html import escape

    agent = application.submitted_by_agent
    to_agent = bool(agent and agent.user and agent.user.email)
    if not to_agent and not application.email:
        return None

    documents = list(application.documents.all())
    facts = []
    if to_agent:
        facts.append(("Student", application.full_name))
    facts += [
        ("Reference", application.reference),
        ("University", application.institution.name if application.institution else "To be confirmed"),
        ("Documents verified", str(len(documents))),
    ]
    items = [(doc.name, "Verified") for doc in documents]

    if to_agent:
        greeting = f"Hello {_first_name(agent.user.full_name, 'there')},"
        opening = (
            f"Every document you uploaded for <strong>{escape(application.full_name)}</strong> "
            "has been checked and verified by our admissions desk."
        )
        recipients, link = [agent.user.email], ("Open the student's file", _url("/agent/students"))
        subject = f"All documents verified: {application.full_name} ({application.reference})"
    else:
        greeting = f"Hello {_first_name(application.full_name, 'there')},"
        opening = "Every document you uploaded has been checked and verified by our admissions desk."
        recipients, link = [application.email], ("View your application", _url("/portal/details"))
        subject = f"All your documents are verified ({application.reference})"

    return _send(
        subject=subject,
        recipients=recipients,
        greeting=greeting,
        paragraphs=[opening, "The file now moves on to the university for an admission decision."],
        facts=facts,
        items_intro="Verified documents:",
        items=items,
        action=link,
    )


COMMISSION_REASON = {
    "registration": "the application fee for {name} was confirmed",
    "visa": "visa support for {name} was confirmed as done",
}


def send_commission_credited_email(agent, application, kind, amount):
    """Money landed in the agent's wallet: how much, why, and the new balance."""
    if not agent.user.email:
        return None

    from django.utils import timezone
    from django.utils.html import escape

    wallet = getattr(agent, "wallet", None)
    if wallet is not None:
        wallet.refresh_from_db()
    reason = COMMISSION_REASON.get(kind, "a milestone on {name} was reached").format(
        name=f"<strong>{escape(application.full_name)}</strong>"
    )

    facts = [
        ("Amount", _naira(amount)),
        ("For", "Registration and fee paid" if kind == "registration" else "Visa support completed"),
        ("Student", application.full_name),
        ("Reference", application.reference),
        ("Credited", timezone.localtime().strftime("%d %B %Y, %H:%M")),
    ]
    if wallet is not None:
        facts.append(("Available balance", _naira(wallet.available_balance)))

    items = None
    if kind == "registration":
        items = [("Still to come", "₦50,000 more is added once visa support for this student is confirmed.")]

    return _send(
        subject=f"{_naira(amount)} added to your wallet",
        recipients=[agent.user.email],
        greeting=f"Hello {_first_name(agent.user.full_name, 'there')},",
        paragraphs=[f"{_naira(amount)} has been added to your Gabstep wallet because {reason}."],
        facts=facts,
        items=items,
        action=("Open your wallet", _url("/agent/wallet")),
    )
