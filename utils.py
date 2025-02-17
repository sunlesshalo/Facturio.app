# File: utils.py
"""
This module contains helper functions for:
  - Geocoding: Resolving county and city data.
  - Extracting client details from the Stripe event.
  - Cleaning data by removing empty string values.
  - Building the final invoice payload for SmartBill.
"""

import logging
import re
from datetime import datetime, timezone
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Create a geolocator instance with a custom user agent.
geolocator = Nominatim(user_agent="YourAppName (your_email@example.com)")

def resolve_county_and_city(client_address):
    """
    Determines the county and adjusts the city value based on the provided client address.

    For addresses in Bucharest (Bucuresti/București):
      - Forces county to "Bucuresti".
      - Updates city to a specific sector if found.
      - Uses geocoding to extract sector details if not directly provided.

    For non-Bucharest addresses:
      - Attempts geocoding if the county is missing.

    Returns:
        tuple: (county, city)
    """
    city = client_address.get('city', 'Unknown City')
    country = client_address.get('country', 'Unknown Country')
    line1 = client_address.get('line1', '')
    line2 = client_address.get('line2', '')
    postal_code = client_address.get('postal_code', '')
    county = (client_address.get('state') or '').strip()

    if city.lower() in ['bucuresti', 'bucurești']:
        county = "Bucuresti"
        sector = None
        # Match "Sector X" (X being a number) in the address fields.
        sector_pattern = re.compile(r'Sector\s*\d+', re.IGNORECASE)
        for field in [line1, line2]:
            if field:
                match = sector_pattern.search(field)
                if match:
                    sector = match.group()
                    break
        if sector:
            city = sector
        else:
            query_address = ', '.join(part for part in [line1, city, postal_code, country] if part)
            try:
                location = geolocator.geocode(query_address, addressdetails=True)
                if location:
                    logging.info("Nominatim output for Bucharest: %s", location.raw)
                    address_data = location.raw.get('address', {})
                    sector = address_data.get('city_district') or address_data.get('suburb')
                    city = sector if sector else "Unknown Sector"
                else:
                    city = "Unknown Sector"
            except GeocoderTimedOut:
                logging.error("Geocoding timed out while resolving Bucharest sector.")
                city = "Unknown Sector"
    else:
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

def extract_client_details(stripe_data):
    """
    Extracts client details from the Stripe event data, including name, email, VAT code, and address.

    Returns:
        dict: A dictionary with keys 'name', 'email', 'vatCode', and 'address'.
    """
    logging.info("Extracting client details from stripe_data: %s", stripe_data)

    if not stripe_data or not isinstance(stripe_data, dict):
        logging.error("stripe_data is missing or not a dict!")
        return {
            'name': 'Unknown Client',
            'email': 'unknown@example.com',
            'vatCode': '0000000000000',
            'address': {}
        }
    cust_details = stripe_data.get('customer_details') or {}
    if not cust_details:
        logging.error("No customer_details found in stripe_data!")
    tax_ids = cust_details.get('tax_ids', [])
    vat_code = (
        tax_ids[0]['value']
        if tax_ids and isinstance(tax_ids[0], dict) and 'value' in tax_ids[0]
        else '0000000000000'
    )
    client = {
        'name': cust_details.get('name', 'Unknown Client'),
        'email': cust_details.get('email', 'unknown@example.com'),
        'vatCode': vat_code,
        'address': cust_details.get('address', {})
    }
    logging.info("Extracted client details: %s", client)
    return client

def remove_empty_values(data):
    """
    Recursively removes any key-value pairs (or list items) with empty string ("") values.
    """
    if isinstance(data, dict):
        return {k: remove_empty_values(v) for k, v in data.items() if v != ""}
    elif isinstance(data, list):
        return [remove_empty_values(item) for item in data if item != ""]
    else:
        return data

def build_payload(stripe_data, config):
    """
    Constructs the final invoice payload to be sent to SmartBill.

    Steps:
      1. Extract client details from the Stripe event.
      2. Use geocoding to resolve/adjust county and city data.
      3. Build the full client address.
      4. Format the event timestamp into a date string.
      5. Build product information (and discount, if applicable).
      6. Assemble and clean the complete payload.

    Returns:
        dict: The cleaned payload formatted for SmartBill.
    """
    client = extract_client_details(stripe_data)
    client_address = client.get('address', {})
    county, city = resolve_county_and_city(client_address)

    # Build the full address by combining available address parts.
    address_parts = [
        client_address.get('line1', ''),
        client_address.get('line2', ''),
        client_address.get('postal_code', '')
    ]
    filtered_address = [part for part in address_parts if part]
    full_address = ', '.join(filtered_address)

    # Determine if the client is a taxpayer (e.g., VAT code starts with "RO").
    is_taxpayer = client['vatCode'].startswith('RO')

    # Convert the 'created' timestamp to a formatted date string.
    issue_timestamp = stripe_data.get('created')
    issue_date = datetime.fromtimestamp(issue_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')

    # Build product information as required by SmartBill.
    product = {
        'name': 'Placeholder Product',  # Replace with actual product details.
        'code': '',
        'productDescription': '',
        'isDiscount': False,
        'measuringUnitName': config['measuringUnitName'],
        'currency': config['currency'],
        'quantity': 1,
        'price': stripe_data.get('amount_total', 0) / 100,  # Convert from cents.
        'isTaxIncluded': config['isTaxIncluded'],
        'taxName': config['taxName'],
        'taxPercentage': config['taxPercentage'],
        'saveToDb': config['saveToDb'],
        'isService': config['isService']
    }

    # Process discount information if available.
    discount_obj = None
    if stripe_data.get('discounts'):
        for discount in stripe_data['discounts']:
            promotion_code_id = discount.get('promotion_code')
            if promotion_code_id:
                # For demonstration purposes, create a placeholder promotion code.
                promotion_code = {
                    'code': 'PROMO123',
                    'coupon': {
                        'percent_off': 10,   # Example: 10% discount.
                        'amount_off': None
                    }
                }
                coupon = promotion_code.get('coupon', {})
                if coupon.get('percent_off') is not None:
                    discount_type = 'percentage'
                    discount_value = coupon['percent_off']
                elif coupon.get('amount_off') is not None:
                    discount_type = 'amount'
                    discount_value = coupon['amount_off'] / 100
                else:
                    discount_type = 'unknown'
                    discount_value = 0
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
                break

    # Assemble the payload.
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
        "isDraft": False,      # Indicates whether the invoice is a draft.
        "dueDate": issue_date,  # For this example, due date equals issue date.
        "deliveryDate": "",     # Delivery date left empty.
        "products": [product],   # Products must be provided as an array.
        "payment": {
            "value": stripe_data.get('amount_total', 0) / 100,
            "paymentSeries": "",
            "type": "Card",
            "isCash": False
        }
    }

    # Add discount information if applicable.
    if discount_obj:
        payload["discount"] = discount_obj

    # Remove keys with empty string values.
    payload = remove_empty_values(payload)
    return payload
