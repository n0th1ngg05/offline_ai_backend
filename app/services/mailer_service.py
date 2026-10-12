"""
Generic email sending via Gmail SMTP (aiosmtplib). Knows nothing about OTPs,
users, or any specific email's content — exposes one function,
send_email(to, subject, body), reusable for any future email type (account
activation, notifications, etc.), not just OTPs. The OTP email's actual
subject/body text lives in auth_service.py, which calls this.

Gmail requires 2FA + an App Password for SMTP auth (regular account
passwords are rejected) — see README.md for how to generate one. Until a
real SMTP_PASSWORD is set, settings.SMTP_DEV_MODE defaults to True and this
module prints the email to the console/log instead of actually sending,
so the full login/OTP/reset flow can be exercised end-to-end without
waiting on real Gmail credentials.
"""

import aiosmtplib
from email.message import EmailMessage

from app.core.config import settings


async def send_email(*, to: str, subject: str, body: str) -> None:
    if settings.SMTP_DEV_MODE or not settings.SMTP_PASSWORD:
        print(
            "\n"
            "========== [DEV MODE] EMAIL NOT ACTUALLY SENT ==========\n"
            f"To:      {to}\n"
            f"Subject: {subject}\n"
            f"Body:\n{body}\n"
            "=========================================================\n"
        )
        return

    message = EmailMessage()
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
