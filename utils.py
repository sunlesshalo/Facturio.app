# File: utils.py
"""
This module contains helper functions for processing Stripe event data:
  - Extracting client details.
  - Removing empty values.
  - Building the final invoice payload.

Note: All geocoding functions have been moved to geocoding.py.
"""

import logging
from datetime import datetime, timezone
from geocoding import resolve_county_and_city

def extract_client_details(stripe_data):
    """
    Extracts client details from the Stripe event data.

    Returns:
        dict: Contains keys 'name', 'email', 'vatCode', and 'address'.
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
    Recursively removes key-value pairs or list items with empty string ("") values.
    """
    if isinstance(data, dict):
        return {k: remove_empty_values(v) for k, v in data.items() if v != ""}
    elif isinstance(data, list):
        return [remove_empty_values(item) for item in data if item != ""]
    else:
        return data

def build_payload(stripe_data, config):
    """
    Constructs the final invoice payload for SmartBill using the Stripe event data.

    Steps:
      1. Extract client details.
      2. Resolve county and city using the geocoding module.
      3. Build the full client address.
      4. Format the event's creation timestamp.
      5. Build product and discount details.
      6. Assemble and clean the payload.

    In TEST_MODE, the payment details are omitted.

    Returns:
        dict: The cleaned invoice payload.
    """
    client = extract_client_details(stripe_data)
    client_address = client.get('address', {})

    # Resolve county and city using the geocoding functions.
    county, city = resolve_county_and_city(client_address)

    # Build the full address from available parts.
    address_parts = [
        client_address.get('line1', ''),
        client_address.get('line2', ''),
        client_address.get('postal_code', '')
    ]
    filtered_address = [part for part in address_parts if part]
    full_address = ', '.join(filtered_address)

    # Determine if the client is a taxpayer (e.g., VAT code starts with "RO").
    is_taxpayer = client['vatCode'].startswith('RO')

    # Format the creation timestamp.
    issue_timestamp = stripe_data.get('created')
    issue_date = datetime.fromtimestamp(issue_timestamp, tz=timezone.utc).strftime('%Y-%m-%d')

    # Build product details.
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

    discount_obj = None
    if stripe_data.get('discounts'):
        for discount in stripe_data['discounts']:
            promotion_code_id = discount.get('promotion_code')
            if promotion_code_id:
                # For demonstration, create a placeholder promotion code.
                promotion_code = {
                    'code': 'PROMO123',
                    'coupon': {
                        'percent_off': 10,  # Example: 10% discount.
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
        "products": [product],
    }

    # Only add payment details if not in test mode.
    if not config.get("TEST_MODE"):
        payload["payment"] = {
            "value": stripe_data.get('amount_total', 0) / 100,
            "paymentSeries": "",
            "type": "Card",
            "isCash": False
        }

    if discount_obj:
        payload["discount"] = discount_obj

    payload = remove_empty_values(payload)
    return payload
