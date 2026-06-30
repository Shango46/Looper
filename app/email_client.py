"""SMTP/IMAP email client for company agents.

Usage:
    from app.email_client import send_email, fetch_emails, test_smtp, test_imap

All functions accept a Company ORM object and read credentials from it.
Passwords are decrypted on the fly — never stored in plaintext in memory longer than needed.
"""
from __future__ import annotations

import email as _email_lib
import imaplib
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Company

logger = logging.getLogger("looper.email")


def _smtp_password(company: "Company") -> str:
    if not company.email_smtp_password_encrypted:
        return ""
    from app.crypto import decrypt
    return decrypt(company.email_smtp_password_encrypted)


def _imap_password(company: "Company") -> str:
    if not company.email_imap_password_encrypted:
        return ""
    from app.crypto import decrypt
    return decrypt(company.email_imap_password_encrypted)


# ── SMTP ──────────────────────────────────────────────────────────────────────

def send_email(
    company: "Company",
    to: str | list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    cc: str | list[str] | None = None,
    reply_to: str | None = None,
) -> None:
    """Send an email using the company's SMTP settings.

    Raises ValueError if SMTP is not configured.
    Raises smtplib.SMTPException on send failure.
    """
    if not company.email_smtp_host or not company.email_smtp_username:
        raise ValueError("SMTP not configured for this company")

    host = company.email_smtp_host
    port = company.email_smtp_port or 587
    username = company.email_smtp_username
    password = _smtp_password(company)
    display_name = company.email_display_name or username
    use_tls = company.email_smtp_use_tls

    to_list = [to] if isinstance(to, str) else to
    cc_list = ([cc] if isinstance(cc, str) else cc) if cc else []

    msg = MIMEMultipart("alternative") if html_body else MIMEText(body, "plain", "utf-8")
    msg["From"] = f"{display_name} <{username}>"
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject

    if html_body:
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = to_list + cc_list

    if use_tls:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(username, password)
            s.sendmail(username, recipients, msg.as_string())
    else:
        with smtplib.SMTP_SSL(host, port, timeout=15) as s:
            s.login(username, password)
            s.sendmail(username, recipients, msg.as_string())

    logger.info("Email sent to %s via %s", recipients, host)


def test_smtp(company: "Company") -> tuple[bool, str]:
    """Test SMTP connectivity. Returns (ok, message)."""
    if not company.email_smtp_host or not company.email_smtp_username:
        return False, "SMTP host and username are required"
    try:
        host = company.email_smtp_host
        port = company.email_smtp_port or 587
        username = company.email_smtp_username
        password = _smtp_password(company)
        use_tls = company.email_smtp_use_tls
        if use_tls:
            with smtplib.SMTP(host, port, timeout=10) as s:
                s.ehlo()
                s.starttls()
                s.login(username, password)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=10) as s:
                s.login(username, password)
        return True, f"Connected to {host}:{port} successfully"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed — check username and password"
    except smtplib.SMTPConnectError as e:
        return False, f"Could not connect to {company.email_smtp_host}: {e}"
    except Exception as e:
        return False, str(e)


# ── IMAP ──────────────────────────────────────────────────────────────────────

def fetch_emails(
    company: "Company",
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> list[dict]:
    """Fetch emails from the company's IMAP account.

    Returns a list of dicts with keys: uid, subject, from, to, date, body, is_read.
    Raises ValueError if IMAP is not configured.
    """
    if not company.email_imap_host or not company.email_imap_username:
        raise ValueError("IMAP not configured for this company")

    host = company.email_imap_host
    port = company.email_imap_port or 993
    username = company.email_imap_username
    password = _imap_password(company)
    use_ssl = company.email_imap_use_ssl

    M = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    try:
        M.login(username, password)
        M.select(folder, readonly=True)

        search_criteria = "UNSEEN" if unread_only else "ALL"
        _, data = M.search(None, search_criteria)
        uids = data[0].split()
        uids = uids[-limit:]  # most recent N

        results = []
        for uid in reversed(uids):
            _, msg_data = M.fetch(uid, "(RFC822)")
            raw = msg_data[0][1]
            msg = _email_lib.message_from_bytes(raw)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            results.append({
                "uid": uid.decode(),
                "subject": msg.get("Subject", "(no subject)"),
                "from": msg.get("From", ""),
                "to": msg.get("To", ""),
                "date": msg.get("Date", ""),
                "body": body,
            })
        return results
    finally:
        try:
            M.logout()
        except Exception:
            pass


def test_imap(company: "Company") -> tuple[bool, str]:
    """Test IMAP connectivity. Returns (ok, message)."""
    if not company.email_imap_host or not company.email_imap_username:
        return False, "IMAP host and username are required"
    try:
        host = company.email_imap_host
        port = company.email_imap_port or 993
        username = company.email_imap_username
        password = _imap_password(company)
        use_ssl = company.email_imap_use_ssl
        M = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
        M.login(username, password)
        M.logout()
        return True, f"Connected to {host}:{port} successfully"
    except imaplib.IMAP4.error as e:
        return False, f"IMAP error: {e}"
    except Exception as e:
        return False, str(e)
