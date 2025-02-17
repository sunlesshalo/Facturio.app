# File: app.py
"""
Main Flask application file with enhanced error handling, retries, logging,
notifications, and idempotency checks using Replit DB.
"""

import json
import logging
from flask import Flask, request, jsonify
import stripe
from config import config, STRIPE_WEBHOOK_SECRET
from utils import build_payload
from smartbill import create_smartbill_invoice, delete_smartbill_invoice
from idempotency import is_event_processed, mark_event_processed, remove_event
from notifications import notify_admin

# Configure logging – in production you might configure logging to a file or an external system.
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

    # Use Replit DB for idempotency: check if the event was already processed.
    event_id = event.get("id")
    if is_event_processed(event_id):
        logger.info("Duplicate event received: %s. Ignoring.", event_id)
        return jsonify(success=True, message="Duplicate event"), 200

    # Mark event as processed.
    mark_event_processed(event_id)

    try:
        if event.get("type") == "checkout.session.completed":
            session = event["data"]["object"]
            final_payload = build_payload(session, config)
            logger.info("Final payload built: %s", json.dumps(final_payload, indent=2))
            invoice_response = create_smartbill_invoice(final_payload)
            logger.info("SmartBill Invoice Response: %s", json.dumps(invoice_response, indent=2))
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
        # Remove the event from idempotency store to allow reprocessing.
        remove_event(event_id)
        return jsonify(success=False, error="Internal server error"), 500

    return jsonify(success=True), 200

if __name__ == "__main__":
    port = 8080
    app.run(host="0.0.0.0", port=port)
