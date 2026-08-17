# utils/email.py
import os
import resend
from typing import Optional

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@hooghlyconv.streamlit.app")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://hooghlyconv.streamlit.app")

resend.api_key = RESEND_API_KEY

def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    try:
        params = {
            "from": FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html_body,
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        # Log the error but do not expose internal details
        print(f"Email send error: {e}")
        return False

def send_verification_email(user_email: str, verification_link: str) -> bool:
    subject = "Verify your email address"
    html = f"""
    <h2>Welcome to VB‑G RAM G Portal</h2>
    <p>Please click the button below to verify your email address.</p>
    <a href="{verification_link}" style="...">Verify My Email</a>
    <p>This link expires in 24 hours.</p>
    """
    return send_email(user_email, subject, html)

def send_otp_email(user_email: str, otp: str) -> bool:
    subject = "Your login verification code"
    html = f"""
    <h2>Login Verification</h2>
    <p>Your one‑time code is:</p>
    <h1 style="...">{otp}</h1>
    <p>This code expires in 5 minutes.</p>
    """
    return send_email(user_email, subject, html)

def send_reset_email(user_email: str, reset_link: str) -> bool:
    subject = "Reset your password"
    html = f"""
    <h2>Password Reset Request</h2>
    <p>Click the link below to reset your password.</p>
    <a href="{reset_link}">Reset Password</a>
    <p>This link expires in 1 hour.</p>
    """
    return send_email(user_email, subject, html)
