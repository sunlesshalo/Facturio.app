# File: config.py
"""
This configuration file contains non-sensitive default settings for the invoice payload,
plus loads sensitive credentials from environment variables (Replit secrets).
"""

import os

# Non-sensitive configuration settings.
config = {
    "companyVatCode": "40670956",       # Company's VAT code
    "seriesName": "RO",                 # Invoice series name (e.g., "RO" for Romania)
    "measuringUnitName": "buc",         # Default measuring unit ("bucăți")
    "currency": "RON",                  # Default currency (Romanian Leu)
    "taxName": "Normala",               # Default tax name
    "taxPercentage": 19,                # Default tax percentage (19%)
    "saveToDb": False,                  # Whether to save payloads to your database
    "isService": True,                  # Whether the product is considered a service
    "isTaxIncluded": False,             # Whether tax is included (based on your settings)
    "SMARTBILL_INVOICE_ENDPOINT": "https://ws.smartbill.ro/SBORO/api/invoice"  # SmartBill API endpoint
}

# Sensitive data – these should be set as environment variables (Replit secrets).
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
SMARTBILL_USERNAME    = os.environ.get("SMARTBILL_USERNAME")
SMARTBILL_TOKEN       = os.environ.get("SMARTBILL_TOKEN")
