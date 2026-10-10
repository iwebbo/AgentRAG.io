"""
Notification service.

  - in-app : row in `notifications` (inbox + unread badge in the UI)
  - email  : platform SMTP (SMTP_* settings), sent to the user's account email

This is deliberately independent from EmailService (IMAP/SMTP with the
per-agent mailbox credentials).
"""
import html as html_lib
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple
from uuid import UUID

import markdown
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.scheduler import Notification

logger = logging.getLogger(__name__)

MAX_STORED_BODY = 20_000
MAX_EMAIL_BODY = 8_000


# ─────────────────────────────── SMTP ────────────────────────────────────────

def smtp_enabled() -> bool:
    s = get_settings()
    return bool(s.SMTP_HOST and (s.SMTP_FROM or s.SMTP_USER))


def _from_address() -> str:
    s = get_settings()
    return s.SMTP_FROM or s.SMTP_USER


def run_link(run_id: Optional[UUID]) -> Optional[str]:
    base = (get_settings().APP_BASE_URL or "").strip().rstrip("/")
    if not base or not run_id:
        return None
    return f"{base}/scheduler?run={run_id}"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "\n\n[…truncated]"


def _render_html(title: str, body_md: str, link: Optional[str]) -> str:
    # Neutralise raw HTML coming from agent output (web content, emails...)
    safe_md = (body_md or "").replace("<", "&lt;")
    rendered = markdown.markdown(safe_md, extensions=["extra", "sane_lists"])
    # Drop remote images (tracking pixels) and non-http(s)/mailto links
    rendered = re.sub(r"<img[^>]*>", "", rendered, flags=re.IGNORECASE)
    rendered = re.sub(
        r'href="(?!https?:|mailto:)[^"]*"', 'href="#"', rendered, flags=re.IGNORECASE
    )
    button = ""
    if link:
        button = (
            f'<p style="margin-top:24px"><a href="{html_lib.escape(link, quote=True)}" '
            'style="background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;'
            'text-decoration:none;font-weight:600">Open in AgentRAG.io</a></p>'
        )
    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;'
        'font-size:14px;line-height:1.5;color:#111;max-width:720px">'
        f'<h2 style="margin:0 0 12px">{html_lib.escape(title)}</h2>'
        f"{rendered}{button}"
        '<hr style="margin-top:28px;border:none;border-top:1px solid #ddd">'
        '<p style="color:#888;font-size:12px">Sent by AgentRAG.io Scheduler</p>'
        "</div>"
    )


def send_email(to: str, subject: str, body_md: str, link: Optional[str] = None) -> None:
    """Send one email through the platform SMTP. Raises on failure."""
    s = get_settings()
    subject = re.sub(r"[\r\n]+", " ", subject).strip()[:200]
    text_body = _clip(body_md or "", MAX_EMAIL_BODY)
    if link:
        text_body += f"\n\nOpen in AgentRAG.io: {link}"

    msg = EmailMessage()
    msg["From"] = _from_address()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(
        _render_html(subject, _clip(body_md or "", MAX_EMAIL_BODY), link), subtype="html"
    )

    if s.SMTP_VERIFY_CERT:
        context = ssl.create_default_context()
    else:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    if s.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(s.SMTP_HOST, s.SMTP_PORT, timeout=30, context=context)
    else:
        server = smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=30)

    with server:
        if not s.SMTP_USE_SSL and s.SMTP_STARTTLS:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        if s.SMTP_USER:
            server.login(s.SMTP_USER, s.SMTP_PASSWORD)
        server.send_message(msg)


# ─────────────────────────────── Dispatch ────────────────────────────────────

def _deliver_email(user_email: Optional[str], title: str, body_md: str, run_id: Optional[UUID]) -> Tuple[str, Optional[str]]:
    if not smtp_enabled():
        return "skipped", "SMTP is not configured on the platform"
    if not user_email:
        return "skipped", "The user account has no email address"
    try:
        send_email(user_email, title, body_md, run_link(run_id))
        return "sent", None
    except Exception as exc:  # network, auth, TLS...
        logger.error("Notification email to %s failed: %s", user_email, exc)
        return "failed", str(exc)[:500]


def notify(
    db: Session,
    *,
    user,
    type_: str,
    title: str,
    body_md: str,
    run_id: Optional[UUID] = None,
    channels: Optional[Iterable[str]] = None,
    force_in_app: bool = False,
) -> Notification:
    """
    Create the inbox record and, if requested, send the email.

    The inbox record is always created (it is also the delivery log); it is
    marked as already read when the user did not select the in-app channel,
    so that it does not raise the unread badge.
    """
    selected = set(channels or ["in_app"])
    wants_in_app = "in_app" in selected or force_in_app

    notification = Notification(
        user_id=user.id,
        type=type_,
        title=(title or "")[:255],
        body=_clip(body_md or "", MAX_STORED_BODY),
        run_id=run_id,
        is_read=not wants_in_app,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    if "email" in selected:
        status, error = _deliver_email(getattr(user, "email", None), title, body_md or "", run_id)
        notification.email_status = status
        notification.email_error = error
        db.commit()

    return notification
