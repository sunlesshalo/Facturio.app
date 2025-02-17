# File: app.py
"""
This is the main Flask application file.

It:
  - Initializes the Flask server.
  - Defines the root endpoint.
  - Defines the /stripe-webhook endpoint that:
      1. Receives and verifies Stripe webhook events.
      2. Processes checkout.session.completed events.
      3. Builds the invoice payload.
      4. Calls the SmartBill API to create the invoice.
"""

import json
import logging
from flask import Flask, request, jsonify
import stripe
from config import config, STRIPE_WEBHOOK_SECRET
from utils import build_payload
from smartbill import create_smartbill_invoice

# Configure logging with timestamps.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

@app.route("/")
def index():
    """
    Root route that returns a welcome message.
    """
    return "Welcome to the Stripe-SmartBill Webhook Service."

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """
    Endpoint to receive and process webhook events from Stripe.

    Workflow:
      1. Retrieve the raw payload and the Stripe-Signature header.
      2. Verify the event using Stripe's library and the webhook secret.
      3. Log the full event details.
      4. For checkout.session.completed events:
           - Build the invoice payload.
           - Create the invoice via the SmartBill API.
      5. Return a success response for handled/unhandled event types.
    """
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logging.error("Webhook error: %s", e)
        return jsonify(success=False, error=str(e)), 400

    logging.info("Full Stripe event: %s", json.dumps(event, indent=2))

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        final_payload = build_payload(session, config)
        logging.info("Final Payload:\n%s", json.dumps(final_payload, indent=2))
        invoice_response = create_smartbill_invoice(final_payload)
        logging.info("SmartBill Invoice Response:\n%s", json.dumps(invoice_response, indent=2))
        return jsonify(success=True, invoice_response=invoice_response), 200
    else:
        logging.info("Unhandled event type: %s", event.get("type"))
        return jsonify(success=True), 200

if __name__ == "__main__":
    port = 8080
    app.run(host="0.0.0.0", port=port)
