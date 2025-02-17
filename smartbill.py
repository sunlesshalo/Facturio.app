# File: smartbill.py
"""
This module handles integration with the SmartBill API.
It sends the constructed invoice payload to SmartBill for invoice creation.
"""

import base64
import logging
import requests
from config import config, SMARTBILL_USERNAME, SMARTBILL_TOKEN

def create_smartbill_invoice(invoice_payload):
    """
    Sends the invoice payload to the SmartBill API.

    Steps:
      1. Prepares HTTP headers using Basic Authentication (with encoded credentials).
      2. Sends a POST request with the invoice payload.
      3. Logs and returns the response.

    Returns:
        dict or None: JSON response from SmartBill if successful; otherwise, None.
    """
    # Prepare Basic Authentication credentials.
    credentials = f"{SMARTBILL_USERNAME}:{SMARTBILL_TOKEN}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    endpoint = config['SMARTBILL_INVOICE_ENDPOINT']
    response = requests.post(endpoint, headers=headers, json=invoice_payload)
    if response.status_code in (200, 201):
        logging.info("Invoice created successfully in SmartBill.")
        return response.json()
    else:
        logging.error("Failed to create invoice in SmartBill. Status code: %s", response.status_code)
        logging.error("Response: %s", response.text)
        return None
