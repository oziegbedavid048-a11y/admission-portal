"""Transactional email.

The design is deliberately plain: a line of sender text, the message, a link,
and one line of footer. No banner, no coloured panels, no marketing furniture.
These are records of something that happened to someone's money or their
application, and they are read on a phone in ten seconds, so they are built to
be skimmed rather than admired. Plain HTML also survives Outlook and Gmail
clipping, which an elaborate table layout does not.

Sending happens on a daemon thread so an HTTP response is never held up by SMTP,
and a failure is logged rather than raised: an account is still created if the
mail server is briefly unreachable.
"""

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

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
    return (full_name or "").split(" ")[0] or fallback


def _naira(amount):
    return f"₦{amount:,.0f}"


# ── Rendering ────────────────────────────────────────────────────────

BODY = "margin:0;padding:24px;background:#ffffff;color:#111827;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;"
WRAP = "max-width:560px;margin:0 auto;"
P = "margin:0 0 16px;color:#111827;"
MUTED = "margin:0;color:#6b7280;font-size:13px;"
LINK = "color:#065f46;"


def _render(greeting, paragraphs, facts=None, action=None):
    """One message: a greeting, some sentences, an optional list, one link.

    `facts` is a list of (label, value) pairs rendered as plain rows. `action`
    is a (text, url) pair rendered as a link rather than a button, because a
    link is unambiguous in every client and needs no styling to work.
    """
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
        f'<p style="{MUTED}">Gabstep &middot; '
        f'<a href="mailto:support@gabstep.com" style="{LINK}">support@gabstep.com</a></p>'
        f"</div></body></html>"
    )


def _plain(greeting, paragraphs, facts=None, action=None):
    lines = [greeting, ""]
    lines += [line for text in paragraphs for line in (text, "")]
    if facts:
        lines += [f"{label}: {value}" for label, value in facts]
        lines.append("")
    if action:
        lines += [f"{action[0]}: {action[1]}", ""]
    lines.append("Gabstep, support@gabstep.com")
    return "\n".join(lines)


def _send(subject, recipients, greeting, paragraphs, facts=None, action=None, wait=False):
    return send_async_email(
        subject,
        _plain(greeting, paragraphs, facts, action),
        _render(greeting, paragraphs, facts, action),
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


def send_application_status_update_email(application, notification_text, subject_override=None):
    """Tell whoever owns this file that something moved.

    A file registered through the partner portal belongs to the agent, not the
    student: the agent collected the documents, pays the fee and hands over the
    letters. So the update goes to the agent alone, and the student is never
    written to. A file the applicant opened themselves goes to the applicant.
    """
    institution = application.institution.name if application.institution else "your institution"
    stage = application.current_stage.name if application.current_stage else "In progress"
    agent = application.submitted_by_agent

    if agent and agent.user and agent.user.email:
        _send(
            subject=subject_override
            or f"{application.full_name}: update on {application.reference}",
            recipients=[agent.user.email],
            greeting=f"Hello {_first_name(agent.user.full_name, 'there')},",
            paragraphs=[
                f"There is an update on the file you filed for {application.full_name}.",
                notification_text,
            ],
            facts=[
                ("Student", application.full_name),
                ("Reference", application.reference),
                ("Institution", institution),
                ("Stage", stage),
            ],
            action=("Open the file", _url("/agent/students")),
        )
        return

    if not application.email:
        return

    _send(
        subject=subject_override or f"Update on your application {application.reference}",
        recipients=[application.email],
        greeting=f"Hello {_first_name(application.full_name, 'there')},",
        paragraphs=[notification_text],
        facts=[
            ("Reference", application.reference),
            ("Institution", institution),
            ("Stage", stage),
        ],
        action=("View your application", _url("/portal")),
    )


# ── Ad funding ───────────────────────────────────────────────────────


def send_loan_approved_email(loan):
    user = loan.agent.user
    _send(
        subject=f"Ad funding approved: {_naira(loan.approved_amount)}",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "Your ad funding request has been approved and sent to your registered "
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
        subject="Ad funding request declined",
        recipients=[user.email],
        greeting=f"Hello {_first_name(user.full_name, 'there')},",
        paragraphs=[
            "We could not approve this ad funding request. This is usually because "
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
        facts.append(("Ad funding repaid", _naira(withdrawal.loan_deduction)))
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
