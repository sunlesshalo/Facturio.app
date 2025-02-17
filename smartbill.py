# File: smartbill.py
"""
Enhanced SmartBill integration with retries and detailed logging.
"""

import base64
import logging
import requests
from config import config, SMARTBILL_USERNAME, SMARTBILL_TOKEN
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5), reraise=True)
def create_smartbill_invoice(invoice_payload):
    """
    Sends the invoice payload to the SmartBill API with retries on transient errors.
    """
    credentials = f"{SMARTBILL_USERNAME}:{SMARTBILL_TOKEN}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    endpoint = config['SMARTBILL_INVOICE_ENDPOINT']
    logger.debug("Sending invoice creation request to %s with payload: %s", endpoint, invoice_payload)
    response = requests.post(endpoint, headers=headers, json=invoice_payload)
    if response.status_code in (200, 201):
        logger.info("Invoice created successfully in SmartBill.")
        logger.debug("SmartBill response: %s", response.json())
        return response.json()
    else:
        logger.error("Failed to create invoice. Status code: %s, Response: %s",
                     response.status_code, response.text)
        response.raise_for_status()

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5), reraise=True)
def delete_smartbill_invoice(invoice_number):
    """
    Deletes an invoice in SmartBill with detailed logging.
    Retries on transient errors.
    """
    cif = config['companyVatCode']
    seriesName = config['seriesName']
    # Use lowercase parameter name as required by SmartBill.
    url = f"https://ws.smartbill.ro/SBORO/api/invoice?cif={cif}&seriesname={seriesName}&number={invoice_number}"
    credentials = f"{SMARTBILL_USERNAME}:{SMARTBILL_TOKEN}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    headers = {
         "Content-Type": "application/json",
         "Authorization": f"Basic {encoded_credentials}"
    }
    logger.debug("Deleting invoice at URL: %s with headers: %s", url, headers)
    response = requests.delete(url, headers=headers)
    if response.status_code in (200, 201):
         logger.info("Invoice %s deleted successfully.", invoice_number)
         logger.debug("Deletion response: %s", response.json())
         return response.json()
    else:
         logger.error("Failed to delete invoice %s. Status code: %s, Response: %s",
                      invoice_number, response.status_code, response.text)
         response.raise_for_status()
