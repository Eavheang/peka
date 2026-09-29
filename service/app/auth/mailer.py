import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def mail_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_invitation(to: str, invite_url: str, expire_days: int) -> bool:
    """Email an invitation link. Returns False, never raises, so the invite survives a mail outage."""
    if not mail_configured():
        return False
    message = EmailMessage()
    message["Subject"] = "You're invited to PEKA"
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = to
    message.set_content(
        "You have been invited to join PEKA.\n\n"
        f"Set your password and sign in here (link valid for {expire_days} days):\n{invite_url}\n\n"
        "If you were not expecting this invitation, you can ignore this email."
    )
    try:
        # ponytail: STARTTLS on the configured port (Gmail: smtp.gmail.com:587); add SMTP_SSL for port 465 if needed.
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            server.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Unable to send invitation email to %s", to)
        return False
    return True
