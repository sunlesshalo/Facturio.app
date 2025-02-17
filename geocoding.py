# File: geocoding.py
"""
This module handles geocoding functionality:
  - It normalizes and validates county names.
  - If the provided county value is not recognized as standard, it performs a geocoding lookup
    to identify the correct county.
  - Works for all cases, whether the input county is valid, an alternative name, or completely bogus.
"""

import logging
import re
import unicodedata
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

logger = logging.getLogger(__name__)

# Create a geolocator instance with a custom user agent.
geolocator = Nominatim(user_agent="FacturioApp (ferencz@pinelines.e)")

# Define the list of standard county names (for Romania, adjust as needed).
VALID_COUNTIES = [
    'Alba', 'Arad', 'Arges', 'Bacau', 'Bihor', 'Bistrita-Nasaud', 'Botosani', 'Brasov', 
    'Braila', 'Buzau', 'Caras-Severin', 'Cluj', 'Constanta', 'Covasna', 'Dambovita', 'Dolj', 
    'Galati', 'Giurgiu', 'Gorj', 'Harghita', 'Hunedoara', 'Ialomita', 'Iasi', 'Ilfov', 
    'Maramures', 'Mehedinti', 'Mures', 'Neamt', 'Olt', 'Prahova', 'Satu Mare', 'Salaj', 
    'Sibiu', 'Suceava', 'Teleorman', 'Timis', 'Tulcea', 'Vaslui', 'Valcea', 'Vrancea', 'Bucuresti'
]

def normalize_county(county):
    """
    Normalize a county name by removing diacritical marks, extra spaces,
    and capitalizing it properly.
    """
    normalized = unicodedata.normalize('NFKD', county).encode('ASCII', 'ignore').decode('ASCII')
    return normalized.strip().capitalize()

def validate_county(raw_county, client_address):
    """
    Validates the county value from client_address.

    Strategy:
      1. If a raw county is provided, normalize it.
      2. If the normalized value is in our standard list, return it.
      3. Otherwise, first attempt a geocoding lookup using postal code and country.
      4. If that fails, attempt a lookup using city and country.
      5. Return the best guess (or a default) if all lookups fail.
    """
    if raw_county:
        normalized = normalize_county(raw_county)
        if normalized.lower() in [vc.lower() for vc in VALID_COUNTIES]:
            return normalized
        else:
            logger.info("County '%s' not recognized as standard. Attempting geocoding lookup.", normalized)
    else:
        logger.info("No county provided. Attempting geocoding lookup.")

    # Strategy 1: Try with postal code and country
    postal_code = client_address.get('postal_code', '')
    country = client_address.get('country', '')
    query_address = ', '.join([postal_code, country]).strip(', ')
    logger.debug("Attempting geocoding lookup using postal code: %s", query_address)

    try:
        location = geolocator.geocode(query_address, addressdetails=True)
        if location:
            address_data = location.raw.get('address', {})
            geocoded_county = (address_data.get('county') or 
                               address_data.get('state') or 
                               address_data.get('region') or None)
            if geocoded_county:
                normalized_geo = normalize_county(geocoded_county)
                logger.info("Lookup using postal code returned '%s'.", normalized_geo)
                return normalized_geo
        else:
            logger.warning("Lookup using postal code '%s' returned no result.", query_address)
    except Exception as e:
        logger.exception("Exception during postal code lookup for address: %s", query_address)

    # Strategy 2: Try with city and country
    city = client_address.get('city', '')
    query_address = ', '.join([city, country]).strip(', ')
    logger.debug("Attempting geocoding lookup using city: %s", query_address)
    try:
        location = geolocator.geocode(query_address, addressdetails=True)
        if location:
            address_data = location.raw.get('address', {})
            geocoded_county = (address_data.get('county') or 
                               address_data.get('state') or 
                               address_data.get('region') or 'Unknown County')
            normalized_geo = normalize_county(geocoded_county)
            logger.info("Lookup using city returned '%s'.", normalized_geo)
            return normalized_geo
        else:
            logger.error("Lookup using city '%s' returned no result.", query_address)
    except Exception as e:
        logger.exception("Exception during city lookup for address: %s", query_address)

    # If all lookups fail, fallback to the original raw value (if provided) or default.
    fallback = normalized if raw_county else 'Unknown County'
    logger.error("All geocoding lookups failed. Falling back to '%s'.", fallback)
    return fallback



def resolve_county_and_city(client_address):
    """
    Determines and validates the county and adjusts the city if necessary.

    For Bucharest addresses:
      - Forces county to "Bucuresti" and attempts to extract sector information.

    For other addresses:
      - Uses the validate_county function to ensure the county is standard.

    Returns:
        tuple: (county, city)
    """
    city = client_address.get('city', 'Unknown City')
    country = client_address.get('country', 'Unknown Country')
    line1 = client_address.get('line1', '')
    line2 = client_address.get('line2', '')
    postal_code = client_address.get('postal_code', '')

    # Check for Bucharest addresses.
    if city.lower() in ['bucuresti', 'bucurești']:
        county = "Bucuresti"
        sector = None
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
                    address_data = location.raw.get('address', {})
                    sector_geo = address_data.get('city_district') or address_data.get('suburb')
                    city = sector_geo if sector_geo else "Unknown Sector"
                else:
                    city = "Unknown Sector"
            except GeocoderTimedOut:
                logger.error("Geocoding timed out while resolving Bucharest sector.")
                city = "Unknown Sector"
        return county, city
    else:
        raw_county = client_address.get('state', '')
        county = validate_county(raw_county, client_address)
        return county, city
