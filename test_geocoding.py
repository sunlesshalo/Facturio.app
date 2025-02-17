# File: test_geocoding.py
import unittest
from geocoding import resolve_county_and_city

class TestGeocoding(unittest.TestCase):
    def test_address_with_standard_postal_code(self):
        # Simulated address data with correct postal code and country.
        address = {
            "line1": "Str. Horea 88-90",
            "line2": "Ap. 13",
            "city": "Cluj-Napoca",
            "postal_code": "400275",
            "country": "RO",
            "state": "Kolozsvar"  # This value is non-standard.
        }
        county, city = resolve_county_and_city(address)
        # We expect the geocoding function to override "Kolozsvar" with a standard value,
        # for example "Cluj" (or whatever your geocoding returns for this address).
        self.assertNotEqual(county.lower(), "kolozsvar")
        # Optionally, you can print the results for manual inspection:
        print("Test 1 - County:", county, "City:", city)

    def test_address_without_state(self):
        # Simulated address data missing the 'state' field.
        address = {
            "line1": "Str. Horea 88-90",
            "line2": "Ap. 13",
            "city": "Cluj-Napoca",
            "postal_code": "400275",
            "country": "RO"
        }
        county, city = resolve_county_and_city(address)
        self.assertNotEqual(county, "Unknown County")
        print("Test 2 - County:", county, "City:", city)

if __name__ == '__main__':
    unittest.main()
