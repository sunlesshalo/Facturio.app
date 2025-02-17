# File: app.py
"""
Main Flask application file with enhanced error handling, idempotency, and email notifications.
"""

import json
import logging
import base64
from flask import Flask, request, jsonify
import stripe
from config import config, STRIPE_WEBHOOK_SECRET
from utils import build_payload
from smartbill import create_smartbill_invoice, delete_smartbill_invoice
from idempotency import is_event_processed, mark_event_processed, remove_event
from notifications import notify_admin
from email_sender import send_invoice_email  # New import

# Configure logging.
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/")
def index():
    return "Welcome to Facturio's Stripe-SmartBill Integration Service."

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error("Webhook signature verification failed: %s", e)
        return jsonify(success=False, error="Invalid signature"), 400

    # Idempotency: check if event already processed (using Replit DB)
    event_id = event.get("id")
    if is_event_processed(event_id):
        logger.info("Duplicate event received: %s. Ignoring.", event_id)
        return jsonify(success=True, message="Duplicate event"), 200

    mark_event_processed(event_id)

    try:
        if event.get("type") == "checkout.session.completed":
            session = event["data"]["object"]
            final_payload = build_payload(session, config)
            logger.info("Final payload built: %s", json.dumps(final_payload, indent=2))
            invoice_response = create_smartbill_invoice(final_payload)
            logger.info("SmartBill Invoice Response: %s", json.dumps(invoice_response, indent=2))

            # Send email notification if invoice creation was successful.
            email_payload = {
                "companyVatCode": config["companyVatCode"],
                "seriesName": config["seriesName"],
                "number": invoice_response.get("number"),
                "type": "factura",
                # Base64-encode subject and body text.
                "subject": base64.b64encode("Invoice Notification".encode("utf-8")).decode("utf-8"),
                "to": session.get("customer_details", {}).get("email"),
                "bodyText": base64.b64encode("Your invoice has been created successfully.".encode("utf-8")).decode("utf-8"),
                "emailConfig": {
                    "mailFrom": config.get("SMARTBILL_USERNAME"),
                    "password": config.get("APP_PASSWORD"),
                    "smtpServer": "smtp.gmail.com",
                    "smtpPort": 587,
                    "useTLS": True
                }
            }
            try:
                send_invoice_email(email_payload)
            except Exception as email_err:
                logger.error("Failed to send invoice email: %s", email_err)
                # Optionally notify admin about the email failure.
                notify_admin(email_err)

            # In test mode, attempt invoice deletion.
            if config.get("TEST_MODE"):
                invoice_number = invoice_response.get("number")
                if invoice_number:
                    deletion_result = delete_smartbill_invoice(invoice_number)
                    logger.info("Invoice deletion result: %s", deletion_result)
                else:
                    logger.error("No invoice number found; cannot delete invoice in test mode.")
        else:
            logger.info("Unhandled event type: %s", event.get("type"))
    except Exception as e:
        logger.exception("Error processing event %s: %s", event_id, e)
        notify_admin(e)
        remove_event(event_id)
        return jsonify(success=False, error="Internal server error"), 500

    return jsonify(success=True), 200

if __name__ == "__main__":
    port = 8080
    app.run(host="0.0.0.0", port=port)
