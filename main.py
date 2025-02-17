# File: app.py
"""
Test application that:
  1. Builds an invoice payload from Stripe event data.
  2. Uses geocoding to resolve missing county data.
  3. Adjusts the payload to match SmartBill API requirements:
     - Products are provided as an array ("products": [ { ... } ]).
     - The discount is provided as a single object ("discount": { ... }) if applicable.
     - isTaxIncluded is determined solely by the configuration.
     - Any keys with an empty string ("") are removed.
  4. Creates the invoice in SmartBill.

Note: In production, refactor this into a Flask project with proper route handlers.
"""

# Standard Python modules for working with JSON, logging, regular expressions,
# base64 encoding, and date/time handling.
import json
import logging
import re
import base64
from datetime import datetime, timezone

# Third-party modules:
# - requests: to perform HTTP requests to external APIs.
# - geopy: to perform geocoding (i.e., converting addresses to geographic coordinates)
#   and extract detailed address components.
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# --- NEW IMPORTS FOR WEBHOOK HANDLING ---
# Flask is used to create the HTTP server to listen for Stripe webhooks.
# Stripe library is used for verifying webhook signatures and accessing Stripe API data.
from flask import Flask, request, jsonify
import stripe

# ------------------------------------------
# Logging Configuration
# ------------------------------------------
# Configure the logging module to output log messages with a timestamp, log level, and message.
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# ------------------------------------------
# CONFIGURATION SETTINGS
# ------------------------------------------
# A dictionary of configuration settings for our application.
# These include company details, default settings for the invoice payload,
# and credentials/settings for the SmartBill API.
config = {
    'companyVatCode': '40670956',      # Company's VAT code
    'seriesName': 'RO',                # Series name for the invoice (e.g., "RO" for Romania)
    # 'bcc_email': 'csuszner.ferencz@gmail.com',  # Removed email configuration
    'measuringUnitName': 'buc',        # Default measuring unit (in this case, pieces or "bucăți")
    'currency': 'RON',                 # Default currency (Romanian Leu)
    'taxName': 'Normala',              # Default tax name
    'taxPercentage': 19,               # Default tax percentage (19%)
    'saveToDb': False,                 # Whether to save this payload to your database
    'isService': True,                 # Whether the product is considered a service
    'isTaxIncluded': False,            # isTaxIncluded is based solely on your company's settings.
    # SmartBill API settings:
    'SMARTBILL_USERNAME': 'ferencz@pinelines.eu',
    'SMARTBILL_TOKEN': '003|78e55fc23e59ecaf8c3991f55dd4809c',
    'SMARTBILL_INVOICE_ENDPOINT': 'https://ws.smartbill.ro/SBORO/api/invoice'
}

# ------------------------------------------
# STRIPE WEBHOOK CONFIGURATION
# ------------------------------------------
# This secret is provided by Stripe for verifying the webhook signature.
# Replace it with your actual webhook secret.
STRIPE_WEBHOOK_SECRET = "whsec_URHeynFoQXMEk0pwDLzOQQTv5BEqJWf2"

# ------------------------------------------
# GEOCODING FUNCTION SETUP
# ------------------------------------------
# Create a geolocator object using the Nominatim service.
# The user_agent should be a string identifying your application.
geolocator = Nominatim(user_agent="YourAppName (your_email@example.com)")

def resolve_county_and_city(client_address):
    """
    Determines the county and adjusts the city value based on the provided client address.

    For addresses in Bucharest (Bucuresti/București):
      - The county is forcefully set to "Bucuresti".
      - The city is updated to a specific sector (e.g., "Sector 3") if that information can be extracted.
      - If no sector is found, a geocoding lookup via Nominatim is performed.

    For non-Bucharest addresses:
      - If the county (state) information is missing, a geocoding lookup is performed to attempt to resolve it.

    Parameters:
        client_address (dict): Address details extracted from the Stripe event.

    Returns:
        tuple: A tuple containing (county, city).
    """
    # Get basic address parts with defaults.
    city = client_address.get('city', 'Unknown City')
    country = client_address.get('country', 'Unknown Country')
    line1 = client_address.get('line1', '')
    line2 = client_address.get('line2', '')
    postal_code = client_address.get('postal_code', '')

    # Try to get the county from the 'state' field; strip any surrounding whitespace.
    county = (client_address.get('state') or '').strip()

    # Check if the city is Bucharest (in Romanian, may be spelled as "București").
    if city.lower() in ['bucuresti', 'bucurești']:
        # For Bucharest, force county to "Bucuresti"
        county = "Bucuresti"
        sector = None
        # Compile a regular expression pattern to match "Sector X" (X being a number).
        sector_pattern = re.compile(r'Sector\s*\d+', re.IGNORECASE)
        # Check both line1 and line2 for a sector match.
        for field in [line1, line2]:
            if field:
                match = sector_pattern.search(field)
                if match:
                    sector = match.group()
                    break
        if sector:
            # If a sector was found, set city to that sector.
            city = sector
        else:
            # If no sector was found, construct a query address and use geocoding to try to extract it.
            query_address = ', '.join(part for part in [line1, city, postal_code, country] if part)
            try:
                location = geolocator.geocode(query_address, addressdetails=True)
                if location:
                    logging.info("Nominatim output for Bucharest: %s", location.raw)
                    address_data = location.raw.get('address', {})
                    # Attempt to retrieve sector information from the geocoding response.
                    sector = address_data.get('city_district') or address_data.get('suburb')
                    if sector:
                        city = sector
                    else:
                        city = "Unknown Sector"
                else:
                    city = "Unknown Sector"
            except GeocoderTimedOut:
                logging.error("Geocoding timed out while resolving Bucharest sector.")
                city = "Unknown Sector"
    else:
        # For non-Bucharest addresses, if the county is missing, attempt geocoding.
        if not county:
            query_address = ', '.join(part for part in [line1, city, postal_code, country] if part)
            try:
                location = geolocator.geocode(query_address, addressdetails=True)
                if location:
                    logging.info("Nominatim output: %s", location.raw)
                    address_data = location.raw.get('address', {})
                    county = (address_data.get('county')
                              or address_data.get('state')
                              or address_data.get('region')
                              or 'Unknown County')
                else:
                    county = 'Unknown County'
            except GeocoderTimedOut:
                logging.error("Geocoding timed out while resolving county for non-Bucharest address.")
                county = 'Unknown County'
    return county, city

# ------------------------------------------
# CLIENT DETAILS EXTRACTION FUNCTION
# ------------------------------------------
def extract_client_details(stripe_data):
    """
    Extracts client details from the Stripe event data.

    This function pulls out the customer's name, email, VAT code (if any),
    and address from the 'customer_details' field in the Stripe event.

    Parameters:
        stripe_data (dict): The dictionary containing Stripe event data.

    Returns:
        dict: A dictionary with keys 'name', 'email', 'vatCode', and 'address'.
    """
    # Log the incoming Stripe data for debugging.
    logging.info("Extracting client details from stripe_data: %s", stripe_data)

    # Validate that stripe_data is a dictionary.
    if not stripe_data or not isinstance(stripe_data, dict):
        logging.error("stripe_data is missing or not a dict!")
        return {
            'name': 'Unknown Client',
            'email': 'unknown@example.com',
            'vatCode': '0000000000000',
            'address': {}
        }

    # Retrieve customer details; if missing, default to an empty dictionary.
    cust_details = stripe_data.get('customer_details') or {}
    if not cust_details:
        logging.error("No customer_details found in stripe_data!")

    # Safely extract tax IDs. If no valid tax_ids are found, use a default VAT code.
    tax_ids = cust_details.get('tax_ids', [])
    vat_code = (
        tax_ids[0]['value']
        if tax_ids and isinstance(tax_ids[0], dict) and 'value' in tax_ids[0]
        else '0000000000000'
    )

    # Build the client details dictionary.
    client = {
        'name': cust_details.get('name', 'Unknown Client'),
        'email': cust_details.get('email', 'unknown@example.com'),
        'vatCode': vat_code,
        'address': cust_details.get('address', {})
    }

    logging.info("Extracted client details: %s", client)
    return client

# ------------------------------------------
# HELPER FUNCTION: Remove Empty Values
# ------------------------------------------
def remove_empty_values(data):
    """
    Recursively removes any key-value pairs from a dictionary (or items from a list)
    where the value is an empty string ("").

    This is useful to clean the payload so that no keys with empty values are sent.

    Parameters:
        data (dict or list): The data to be cleaned.

    Returns:
        dict or list: The cleaned data with no empty string values.
    """
    if isinstance(data, dict):
        # Recurse into dictionaries and only keep items where the value is not an empty string.
        return {k: remove_empty_values(v) for k, v in data.items() if v != ""}
    elif isinstance(data, list):
        # Recurse into list items.
        return [remove_empty_values(item) for item in data if item != ""]
    else:
        # For non-dict/list types, return the value as-is.
        return data

# ------------------------------------------
# PAYLOAD BUILDING FUNCTION
# ------------------------------------------
def build_payload(stripe_data, config):
    """
    Constructs the final invoice payload to be sent to SmartBill.

    The steps include:
      1. Extract client details from the Stripe event.
      2. Use geocoding to resolve or adjust county and city data.
      3. Build the full client address from available address parts.
      4. Convert the creation timestamp from the event into a formatted date.
      5. Build the product information (and discount, if applicable).
      6. Assemble the complete payload dictionary.
      7. Remove any keys with empty string values from the payload.

    Parameters:
        stripe_data (dict): Stripe event data.
        config (dict): Configuration settings.

    Returns:
        dict: The final, cleaned payload formatted for SmartBill.
    """
    # Extract client details using the helper function.
    client = extract_client_details(stripe_data)
    # Retrieve the client's address.
    client_address = client.get('address', {})

    # Resolve the county and adjust the city name using geocoding logic.
    county, city = resolve_county_and_city(client_address)

    # Build the full address by joining line1, line2, and postal_code.
    address_parts = [
        client_address.get('line1', ''),
        client_address.get('line2', ''),
        client_address.get('postal_code', '')
    ]
    filtered_address = [part for part in address_parts if part]
    full_address = ', '.join(filtered_address)

    # Determine if the client is a taxpayer by checking if their VAT code starts with "RO".
    is_taxpayer = client['vatCode'].startswith('RO')

    # Convert the 'created' timestamp from the Stripe event to a formatted date string.
    issue_timestamp = stripe_data.get('created')
    issue_date = datetime.fromtimestamp(issue_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')

    # Build a product object as required by SmartBill.
    product = {
        'name': 'Placeholder Product',  # Placeholder; replace with actual product details.
        'code': '',
        'productDescription': '',
        'isDiscount': False,
        'measuringUnitName': config['measuringUnitName'],
        'currency': config['currency'],
        'quantity': 1,
        'price': stripe_data.get('amount_total', 0) / 100,  # Convert cents to currency units.
        'isTaxIncluded': config['isTaxIncluded'],
        'taxName': config['taxName'],
        'taxPercentage': config['taxPercentage'],
        'saveToDb': config['saveToDb'],
        'isService': config['isService']
    }

    # Initialize discount_obj to None. If any discount is found, it will be built below.
    discount_obj = None
    if stripe_data.get('discounts'):
        # Loop through discounts in the event (if any).
        for discount in stripe_data['discounts']:
            promotion_code_id = discount.get('promotion_code')
            if promotion_code_id:
                # For demo purposes, we create a placeholder promotion code.
                promotion_code = {
                    'code': 'PROMO123',  # Placeholder promotion code.
                    'coupon': {
                        'percent_off': 10,  # Example discount of 10%.
                        'amount_off': None
                    }
                }
                coupon = promotion_code.get('coupon', {})
                # Determine the discount type and value.
                if coupon.get('percent_off') is not None:
                    discount_type = 'percentage'
                    discount_value = coupon['percent_off']
                elif coupon.get('amount_off') is not None:
                    discount_type = 'amount'
                    discount_value = coupon['amount_off'] / 100
                else:
                    discount_type = 'unknown'
                    discount_value = 0
                # Build the discount object.
                discount_obj = {
                    "name": promotion_code.get('code', 'Unknown Promotion Code'),
                    "isDiscount": True,
                    "numberOfItems": 1,
                    "measuringUnitName": config['measuringUnitName'],
                    "currency": config['currency'],
                    "isTaxIncluded": config['isTaxIncluded'],
                    "taxName": config['taxName'],
                    "taxPercentage": config['taxPercentage'],
                    "discountType": discount_type,
                    "discountValue": discount_value
                }
                break  # Exit after processing the first valid discount.

    # Assemble the final payload to be sent to SmartBill.
    payload = {
        "companyVatCode": config['companyVatCode'],
        "client": {
            "name": client['name'],
            "vatCode": client['vatCode'],
            "isTaxPayer": is_taxpayer,
            "address": full_address,
            "city": city,
            "county": county,
            "country": client_address.get('country', 'Unknown Country'),
            "email": client['email'],
            "saveToDb": config['saveToDb']
        },
        "issueDate": issue_date,
        "seriesName": config['seriesName'],
        "isDraft": False,  # Indicates whether the invoice is a draft.
        # Email-related keys have been removed as per current requirements.
        "dueDate": issue_date,  # In this example, due date is the same as issue date.
        "deliveryDate": "",     # Delivery date left empty.
        "products": [product],  # Products must be provided as an array.
        "payment": {
            "value": stripe_data.get('amount_total', 0) / 100,
            "paymentSeries": "",
            "type": "Card",
            "isCash": False
        }
    }

    # If a discount was applied, add it to the payload.
    if discount_obj:
        payload["discount"] = discount_obj

    # Clean the payload by removing any keys with empty string values.
    payload = remove_empty_values(payload)

    return payload

# ------------------------------------------
# SMARTBILL INVOICE CREATION FUNCTION
# ------------------------------------------
def create_smartbill_invoice(invoice_payload, config):
    """
    Sends the invoice payload to the SmartBill API to create an invoice.

    This function:
      1. Prepares HTTP headers using Basic Authentication (encoding the SmartBill credentials).
      2. Sends a POST request with the invoice payload to the SmartBill API endpoint.
      3. Logs and returns the response from SmartBill.

    Parameters:
        invoice_payload (dict): The payload built from the Stripe event.
        config (dict): Configuration settings containing SmartBill credentials.

    Returns:
        dict or None: The JSON response from SmartBill if successful; otherwise, None.
    """
    # Create credentials string and encode it in base64 for Basic Authentication.
    credentials = f"{config['SMARTBILL_USERNAME']}:{config['SMARTBILL_TOKEN']}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    # Get the SmartBill invoice endpoint from configuration.
    endpoint = config['SMARTBILL_INVOICE_ENDPOINT']
    # Send a POST request to create the invoice.
    response = requests.post(endpoint, headers=headers, json=invoice_payload)
    if response.status_code in (200, 201):
        logging.info("Invoice created successfully in SmartBill.")
        return response.json()  # Return the JSON response if successful.
    else:
        # Log error details if invoice creation fails.
        logging.error("Failed to create invoice in SmartBill. Status code: %s", response.status_code)
        logging.error("Response: %s", response.text)
        return None

# ------------------------------------------
# STRIPE WEBHOOK ENDPOINT & FLASK APP SETUP
# ------------------------------------------
# Create a Flask app instance.
app = Flask(__name__)

@app.route("/")
def index():
    """
    A simple route for the root URL that returns a welcome message.
    """
    return "Welcome to the Stripe-SmartBill Webhook Service."

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """
    Endpoint to receive webhook events from Stripe.

    Steps performed:
      1. Retrieve the raw request payload and the Stripe-Signature header.
      2. Use Stripe's library to construct and verify the event using the webhook secret.
      3. Log the full event details for debugging purposes.
      4. If the event is a checkout.session.completed event:
         - Extract the session data from the event.
         - Build the invoice payload.
         - Call SmartBill API to create the invoice.
         - Log and return the SmartBill response.
      5. For other event types, simply return success.
    """
    # Retrieve the raw payload from the incoming HTTP request.
    payload = request.get_data()
    # Retrieve the signature header sent by Stripe.
    sig_header = request.headers.get("Stripe-Signature")
    try:
        # Verify the event's signature and construct the event object.
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        # Log any errors during webhook verification and return a 400 error response.
        logging.error("Webhook error: %s", e)
        return jsonify(success=False, error=str(e)), 400

    # Log the full event details for debugging purposes.
    logging.info("Full Stripe event: %s", json.dumps(event, indent=2))

    # Process the event only if it is a checkout.session.completed event.
    if event.get("type") == "checkout.session.completed":
        # Extract the checkout session data from the event.
        session = event["data"]["object"]
        # Build the final invoice payload using the session data and configuration.
        final_payload = build_payload(session, config)
        logging.info("Final Payload:\n%s", json.dumps(final_payload, indent=2))
        # Create the invoice in SmartBill using the generated payload.
        invoice_response = create_smartbill_invoice(final_payload, config)
        logging.info("SmartBill Invoice Response:\n%s", json.dumps(invoice_response, indent=2))
        return jsonify(success=True, invoice_response=invoice_response), 200
    else:
        # If the event type is not handled, log it and return success.
        logging.info("Unhandled event type: %s", event.get("type"))
        return jsonify(success=True), 200

# ------------------------------------------
# MAIN EXECUTION: Start the Flask Server
# ------------------------------------------
if __name__ == "__main__":
    # For local testing, use port 8080 or the PORT environment variable if provided.
    port = 8080
    app.run(host="0.0.0.0", port=port)
