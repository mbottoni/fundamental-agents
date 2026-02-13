"""
Email service.

When SMTP is configured, sends real emails.
Otherwise, logs the message to the console (dev mode).
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import settings

logger = logging.getLogger("stock_analyzer.email")


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def _send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email via SMTP or log it in dev mode."""
    if not _smtp_configured():
        logger.info(
            "📧 [DEV MODE] Email to=%s subject='%s'\n%s",
            to, subject, html_body,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_ADDRESS}>"
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_ADDRESS, to, msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)


def send_password_reset_email(email: str, token: str) -> None:
    """Send a password reset link."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"""
    <h2>Password Reset</h2>
    <p>You requested a password reset for your StockAnalyzer AI account.</p>
    <p><a href="{reset_url}" style="background:#3b82f6;color:white;padding:12px 24px;
       text-decoration:none;border-radius:8px;display:inline-block;">
       Reset Password</a></p>
    <p>This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>
    <p style="color:#666;font-size:12px;">Or paste this link: {reset_url}</p>
    """
    _send_email(email, "Reset your password — StockAnalyzer AI", html)


def send_email_verification(email: str, token: str) -> None:
    """Send an email verification link."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""
    <h2>Verify Your Email</h2>
    <p>Welcome to StockAnalyzer AI! Please verify your email address.</p>
    <p><a href="{verify_url}" style="background:#3b82f6;color:white;padding:12px 24px;
       text-decoration:none;border-radius:8px;display:inline-block;">
       Verify Email</a></p>
    <p>This link expires in 24 hours.</p>
    <p style="color:#666;font-size:12px;">Or paste this link: {verify_url}</p>
    """
    _send_email(email, "Verify your email — StockAnalyzer AI", html)
