# File: email_sender.py
"""
This module sends invoice emails using SMTP. It expects an invoice payload with email-related
fields, including base64-encoded subject and body text. For now, this is tailored for our company's use.
"""

import os
import base64
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def send_invoice_email(invoice_payload):
    """
    Sends an invoice email using SMTP.

    The invoice_payload dictionary should contain:
      - companyVatCode: e.g., "RO12345678"
      - seriesName: e.g., "seriesname"
      - number: e.g., "invoicenumber"
      - type: e.g., "factura"
      - subject: Base64EncodedSubject
      - to: recipient email address (from Stripe event details)
      - bodyText: Base64EncodedBody
      - emailConfig: {
            "mailFrom": <sender email from env var SMARTBILL_USERNAME>,
            "password": <app password from env var APP_PASSWORD>,
            "smtpServer": "smtp.gmail.com",
            "smtpPort": 587,
            "useTLS": true
        }

    Returns True if email is sent successfully; raises an exception otherwise.
    """
    try:
        email_config = invoice_payload.get("emailConfig", {})
        # Ensure we have the necessary configuration:
        mail_from = email_config.get("mailFrom") or os.environ.get("SMARTBILL_USERNAME")
        password = email_config.get("password") or os.environ.get("APP_PASSWORD")
        smtp_server = email_config.get("smtpServer", "smtp.gmail.com")
        smtp_port = email_config.get("smtpPort", 587)
        use_tls = email_config.get("useTLS", True)

        recipient = invoice_payload.get("to")
        if not recipient:
            raise ValueError("Recipient email is missing in payload.")

        subject_encoded = invoice_payload.get("subject", "")
        body_text_encoded = invoice_payload.get("bodyText", "")
        if not subject_encoded or not body_text_encoded:
            raise ValueError("Email subject or body is missing.")

        # Decode Base64 subject and body
        try:
            subject = base64.b64decode(subject_encoded).decode("utf-8")
            body_text = base64.b64decode(body_text_encoded).decode("utf-8")
        except Exception as decode_err:
            logger.exception("Failed to decode subject or body: %s", decode_err)
            raise

        # Build the email message.
        msg = MIMEMultipart()
        msg["From"] = mail_from
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))

        logger.debug("Prepared email message: From=%s, To=%s, Subject=%s", mail_from, recipient, subject)

        # Connect to SMTP server.
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(mail_from, password)
        server.sendmail(mail_from, recipient, msg.as_string())
        server.quit()
        logger.info("Invoice email sent successfully to %s.", recipient)
        return True
    except Exception as e:
        logger.exception("Failed to send invoice email: %s", e)
        raise
