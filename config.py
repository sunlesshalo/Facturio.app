# File: config.py
"""
This configuration file contains non-sensitive default settings for the invoice payload.
Sensitive credentials (like Stripe and SmartBill keys) are loaded from environment variables (Replit secrets).
"""

import os

config = {
    "companyVatCode": "40670956",       # Company's VAT code
    "seriesName": "RO",                 # Invoice series name (e.g., "RO" for Romania)
    "measuringUnitName": "buc",         # Default measuring unit (e.g., pieces)
    "currency": "RON",                  # Default currency (Romanian Leu)
    "taxName": "Normala",               # Default tax name
    "taxPercentage": 19,                # Default tax percentage (19%)
    "saveToDb": False,                  # Whether to save payloads to your database
    "isService": True,                  # Whether the product is considered a service
    "isTaxIncluded": False,             # Whether tax is included (based on your settings)
    "SMARTBILL_INVOICE_ENDPOINT": "https://ws.smartbill.ro/SBORO/api/invoice"  # SmartBill API endpoint
}

# Sensitive data – set these as Replit secrets (Environment Variables)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
SMARTBILL_USERNAME    = os.environ.get("SMARTBILL_USERNAME")
SMARTBILL_TOKEN       = os.environ.get("SMARTBILL_TOKEN")

# Optionally, you can add a check so that your app fails early if these are not set:
if not STRIPE_WEBHOOK_SECRET:
    raise ValueError("STRIPE_WEBHOOK_SECRET is not set in the environment variables!")
if not SMARTBILL_USERNAME:
    raise ValueError("SMARTBILL_USERNAME is not set in the environment variables!")
if not SMARTBILL_TOKEN:
    raise ValueError("SMARTBILL_TOKEN is not set in the environment variables!")
