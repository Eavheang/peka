import logging
import smtplib
from email.message import EmailMessage
from html import escape

from app.config import settings

logger = logging.getLogger(__name__)

# Colours mirror the webclient theme (app/globals.css).
_BACKGROUND, _INK, _PRIMARY, _PANEL = "#f4f0e8", "#181a19", "#e96243", "#202523"
_PANEL_INK, _MUTED, _BORDER, _SUCCESS = "#f3f1ea", "#767872", "#d8d3c9", "#a9c4a0"
_FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
_MONO = "'SFMono-Regular',Menlo,Consolas,monospace"


def mail_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def _invitation_text(invite_url: str, expire_days: int, role: str) -> str:
    return (
        f"You have been invited to join PEKA as {role}.\n\n"
        f"Set your password and sign in here (link valid for {expire_days} days):\n{invite_url}\n\n"
        "If you were not expecting this invitation, you can ignore this email."
    )


def _invitation_html(invite_url: str, expire_days: int, role: str) -> str:
    # Table layout and inline styles only: the subset every mail client renders.
    url, role = escape(invite_url, quote=True), escape(role.title())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>You're invited to PEKA</title>
</head>
<body style="margin:0;padding:0;background:{_BACKGROUND};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">Set your password and start using PEKA.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BACKGROUND};">
<tr><td align="center" style="padding:32px 16px;">
  <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;border:1px solid {_BORDER};border-radius:16px;overflow:hidden;background:#ffffff;">
    <tr><td style="background:{_PANEL};padding:32px 32px 36px;">
      <div style="font-family:{_FONT};font-size:22px;font-weight:700;letter-spacing:-0.06em;color:{_PANEL_INK};">peka</div>
      <div style="margin-top:28px;font-family:{_MONO};font-size:11px;letter-spacing:0.16em;text-transform:uppercase;color:{_PRIMARY};">You&#8217;re invited</div>
      <div style="margin-top:10px;font-family:{_FONT};font-size:28px;line-height:1.15;font-weight:700;letter-spacing:-0.04em;color:{_PANEL_INK};">Good answers start with <span style="color:{_SUCCESS};">the right context.</span></div>
    </td></tr>
    <tr><td style="padding:32px;font-family:{_FONT};color:{_INK};">
      <p style="margin:0 0 12px;font-size:16px;line-height:1.5;color:{_INK};">You&#8217;ve been invited to join your organisation&#8217;s private knowledge base as <strong>{role}</strong>.</p>
      <p style="margin:0 0 28px;font-size:16px;line-height:1.5;color:#5c605a;">Choose a password to finish setting up your account. You&#8217;ll be signed in automatically.</p>
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="background:{_PRIMARY};border-radius:8px;"><a href="{url}" style="display:inline-block;padding:14px 28px;font-family:{_FONT};font-size:16px;font-weight:700;color:#ffffff;text-decoration:none;">Set your password</a></td>
      </tr></table>
      <p style="margin:28px 0 6px;font-size:13px;line-height:1.5;color:{_MUTED};">Button not working? Paste this link into your browser:</p>
      <p style="margin:0;font-family:{_MONO};font-size:12px;line-height:1.5;color:#5c605a;word-break:break-all;"><a href="{url}" style="color:#5c605a;">{url}</a></p>
    </td></tr>
    <tr><td style="padding:20px 32px;border-top:1px solid {_BORDER};background:{_BACKGROUND};font-family:{_FONT};font-size:12px;line-height:1.5;color:{_MUTED};">
      This link works once and expires in {expire_days} days. If you weren&#8217;t expecting this invitation, you can safely ignore this email.
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""


def send_invitation(to: str, invite_url: str, expire_days: int, role: str) -> bool:
    """Email an invitation link. Returns False, never raises, so the invite survives a mail outage."""
    if not mail_configured():
        return False
    message = EmailMessage()
    message["Subject"] = "You're invited to PEKA"
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = to
    message.set_content(_invitation_text(invite_url, expire_days, role))
    message.add_alternative(_invitation_html(invite_url, expire_days, role), subtype="html")
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
