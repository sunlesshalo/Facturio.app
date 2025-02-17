# File: config.py
"""
This configuration file contains non-sensitive default settings for the invoice payload.
Sensitive credentials (like Stripe and SmartBill keys) are loaded from environment variables (Replit secrets).
Additionally, a TEST_MODE flag is used to alter behavior during testing.
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
    "SMARTBILL_INVOICE_ENDPOINT": "https://ws.smartbill.ro/SBORO/api/invoice"  # Base endpoint for invoice creation
}

# Sensitive data – set these as Replit secrets (Environment Variables)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
SMARTBILL_USERNAME    = os.environ.get("SMARTBILL_USERNAME")
SMARTBILL_TOKEN       = os.environ.get("SMARTBILL_TOKEN")

# Test mode flag: set TEST_MODE=true in Replit secrets (or in your environment) for testing.
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
config["TEST_MODE"] = TEST_MODE

# Fail early if credentials are missing.
if not STRIPE_WEBHOOK_SECRET:
    raise ValueError("STRIPE_WEBHOOK_SECRET is not set in the environment variables!")
if not SMARTBILL_USERNAME:
    raise ValueError("SMARTBILL_USERNAME is not set in the environment variables!")
if not SMARTBILL_TOKEN:
    raise ValueError("SMARTBILL_TOKEN is not set in the environment variables!")
