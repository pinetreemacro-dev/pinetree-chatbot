import logging
import smtplib
from email.message import EmailMessage

from backend.core.config import settings

log = logging.getLogger("chatbot.email")


def send_escalation_email(name: str, email: str, phone: str, question: str, session_id: str, history: list[tuple[str, str]]) -> bool:
    lines = [
        "A chatbot user asked something outside the chatbot's scope.",
        "",
        f"Name: {name}",
        f"Email: {email}",
        f"Phone: {phone}",
        f"Session: {session_id}",
        f"Question: {question}",
        "",
        "Chat history:",
        *[f"  {sender}: {text}" for sender, text in history],
    ]
    if not settings.smtp_host:
        log.warning("SMTP not configured; escalation email not sent:\n%s", "\n".join(lines))
        return False
    msg = EmailMessage()
    msg["Subject"] = "New Chatbot Query Requiring Human Assistance"
    msg["From"] = settings.smtp_user or settings.escalation_email
    msg["To"] = settings.escalation_email
    msg["Reply-To"] = email
    msg.set_content("\n".join(lines))
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("Failed to send escalation email")
        return False
