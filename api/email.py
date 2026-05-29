"""Email delivery for magic-link auth.

Production: configure ``SMTP_HOST`` / ``SMTP_PORT`` / ``SMTP_USER`` /
``SMTP_PASSWORD`` / ``SMTP_FROM``. We send via ``aiosmtplib`` with STARTTLS.

Dev: leave SMTP_HOST unset and the link is printed to stdout with a
``[DEV-MAGIC-LINK]`` marker so it's easy to grep out of server logs.
"""

from __future__ import annotations

import logging
import os
from email.message import EmailMessage

log = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@studyevaluator.local")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"


async def send_magic_link(email: str, link: str) -> None:
    body = (
        "Hi,\n\n"
        "Click the link below to sign in to StudyEvaluator. "
        "It's valid for 15 minutes.\n\n"
        f"{link}\n\n"
        "If you didn't request this, you can ignore the email.\n"
    )
    if not SMTP_HOST:
        print(f"[DEV-MAGIC-LINK] {email} -> {link}", flush=True)
        return

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg["Subject"] = "Your StudyEvaluator sign-in link"
    msg.set_content(body)

    import aiosmtplib

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=SMTP_USE_TLS,
    )
    log.info("Sent magic link to %s", email)
