# File: geocoding.py
"""
This module handles geocoding functionality:
  - It initializes a Nominatim geolocator.
  - It validates and normalizes county names.
  - It resolves county and city data from an address.

County names are first normalized (i.e. diacritical marks are removed, capitalization fixed)
and then checked against a predefined list of valid counties.
If the county value is missing or invalid, the code attempts to use geocoding to correct it.
"""

import logging
import re
import unicodedata
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Initialize the geolocator with a custom user agent.
geolocator = Nominatim(user_agent="YourAppName (your_email@example.com)")

# Predefined list of valid counties (example for Romania). Adjust as needed.
VALID_COUNTIES = [
    'Alba', 'Arad', 'Arges', 'Bacau', 'Bihor', 'Bistrita-nasaud', 'Botosani', 'Brasov', 
    'Braila', 'Buzau', 'Caras-severin', 'Cluj', 'Constanta', 'Covasna', 'Dambovita', 'Dolj', 
    'Galati', 'Giurgiu', 'Gorj', 'Harghita', 'Hunedoara', 'Ialomita', 'Iasi', 'Ilfov', 
    'Maramures', 'Mehedinti', 'Mures', 'Neamt', 'Olt', 'Prahova', 'Satu mare', 'Salaj', 
    'Sibiu', 'Suceava', 'Teleorman', 'Timis', 'Tulcea', 'Vaslui', 'Valcea', 'Vrancea', 'Bucuresti'
]

def normalize_county(county):
    """
    Normalize a county name by removing diacritical marks, extra spaces,
    and ensuring proper capitalization.
    """
    normalized = unicodedata.normalize('NFKD', county).encode('ASCII', 'ignore').decode('ASCII')
    normalized = normalized.strip().capitalize()
    return normalized

def validate_county(raw_county, client_address):
    """
    Validate and correct the county value.

    If raw_county is provided, normalize it and check if it exists in the valid counties list.
    If it doesn't match (or is made-up), attempt a geocoding lookup using the full address.
    If no county is provided, also attempt geocoding.

    Returns:
        str: The validated (and possibly corrected) county name, or 'Unknown County'.
    """
    if raw_county:
        corrected = normalize_county(raw_county)
        if corrected.lower() in [vc.lower() for vc in VALID_COUNTIES]:
            return corrected
        else:
            logging.info("County '%s' not recognized. Attempting geocoding lookup.", corrected)
    # Build a query address from available parts.
    line1 = client_address.get('line1', '')
    city = client_address.get('city', '')
    postal_code = client_address.get('postal_code', '')
    country = client_address.get('country', '')
    query_address = ', '.join([line1, city, postal_code, country]).strip(', ')

    try:
        location = geolocator.geocode(query_address, addressdetails=True)
        if location:
            address_data = location.raw.get('address', {})
            geocoded_county = address_data.get('county') or address_data.get('state')
            if geocoded_county:
                corrected_geo = normalize_county(geocoded_county)
                if corrected_geo.lower() in [vc.lower() for vc in VALID_COUNTIES]:
                    logging.info("Geocoded county '%s' validated as '%s'.", geocoded_county, corrected_geo)
                    return corrected_geo
                else:
                    logging.info("Geocoded county '%s' not in valid counties list.", corrected_geo)
    except GeocoderTimedOut:
        logging.error("Geocoding timed out while validating county.")
    except Exception as e:
        logging.error("Error during geocoding county: %s", e)

    # If all else fails, return a normalized value (if available) or 'Unknown County'.
    return corrected if raw_county else 'Unknown County'

def resolve_county_and_city(client_address):
    """
    Determines and validates the county and adjusts the city based on the client address.

    For Bucharest:
      - Forces county to "Bucuresti" and attempts to extract the sector (e.g., "Sector 3")
        from the address lines.
      - If no sector is found, uses geocoding to attempt to identify it.

    For non-Bucharest addresses:
      - Uses validate_county to ensure the county is correct.

    Returns:
        tuple: (county, city)
    """
    city = client_address.get('city', 'Unknown City')
    country = client_address.get('country', 'Unknown Country')
    line1 = client_address.get('line1', '')
    line2 = client_address.get('line2', '')
    postal_code = client_address.get('postal_code', '')

    # Check for Bucharest (Bucuresti/București) addresses.
    if city.lower() in ['bucuresti', 'bucurești']:
        county = "Bucuresti"
        sector = None
        # Look for "Sector X" in the address fields.
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
            query_address = ', '.join([line1, city, postal_code, country]).strip(', ')
            try:
                location = geolocator.geocode(query_address, addressdetails=True)
                if location:
                    address_data = location.raw.get('address', {})
                    sector_geo = address_data.get('city_district') or address_data.get('suburb')
                    if sector_geo:
                        city = sector_geo
                    else:
                        city = "Unknown Sector"
                else:
                    city = "Unknown Sector"
            except GeocoderTimedOut:
                logging.error("Geocoding timed out while resolving Bucharest sector.")
                city = "Unknown Sector"
        return county, city
    else:
        raw_county = client_address.get('state', '')
        county = validate_county(raw_county, client_address)
        return county, city
