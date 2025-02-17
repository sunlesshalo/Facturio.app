# File: test_email_sender.py
import os
import base64
from email_sender import send_invoice_email

def test_send_email():

    mailFrom = os.environ.get("SMARTBILL_USERNAME"),
    password = os.environ.get("APP_PASSWORD"),
    # Create a sample payload with Base64 encoded subject and body.
    payload = {
        "companyVatCode": "RO12345678",
        "seriesName": "seriesname",
        "number": "invoicenumber",
        "type": "factura",
        "subject": base64.b64encode("Test Invoice Subject".encode("utf-8")).decode("utf-8"),
        "to": "ferencz@pinelines.eu",  # Replace with a valid test email address.
        "bodyText": base64.b64encode("This is a test invoice email body.".encode("utf-8")).decode("utf-8"),
        "emailConfig": {
            "mailFrom": mailFrom,  # Or rely on env var SMARTBILL_USERNAME
            "password": password,              # Or rely on env var APP_PASSWORD
            "smtpServer": "smtp.gmail.com",
            "smtpPort": 587,
            "useTLS": True
        }
    }
    try:
        result = send_invoice_email(payload)
        print("Email sent successfully:", result)
    except Exception as e:
        print("Email sending failed:", e)

if __name__ == "__main__":
    test_send_email()
