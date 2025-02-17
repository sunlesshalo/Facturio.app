# File: test_invoice_payload.py
import unittest
from datetime import datetime, timezone
from utils import build_payload

class TestInvoicePayload(unittest.TestCase):
    def setUp(self):
        # Standard configuration for tests.
        self.config = {
            "companyVatCode": "40670956",
            "seriesName": "RO",
            "measuringUnitName": "buc",
            "currency": "RON",
            "taxName": "Normala",
            "taxPercentage": 19,
            "saveToDb": False,
            "isService": True,
            "isTaxIncluded": False,
            # You might also include TEST_MODE flag if needed.
            "TEST_MODE": False
        }
        # A standard Stripe event (or session) dictionary.
        # Amount total is in cents.
        self.standard_session = {
            "created": int(datetime(2025, 2, 17, tzinfo=timezone.utc).timestamp()),
            "amount_total": 20000,  # 20,000 cents => 200.00 RON
            "customer_details": {
                "name": "Test Client",
                "email": "client@example.com",
                "tax_ids": [{"value": "RO12345678"}],
                "address": {
                    "line1": "Str. Example 123",
                    "line2": "Ap. 4",
                    "postal_code": "400275",
                    "city": "Cluj-Napoca",
                    "country": "RO",
                    "state": "Cluj"  # Already valid
                }
            }
        }

    def test_standard_payload(self):
        payload = build_payload(self.standard_session, self.config)
        # Verify that the amount conversion is correct.
        self.assertAlmostEqual(payload["products"][0]["price"], 200.00)
        # Check that the issueDate matches the expected formatted date.
        self.assertEqual(payload["issueDate"], "2025-02-17")
        # Verify client email is passed.
        self.assertEqual(payload["client"]["email"], "client@example.com")

    def test_missing_tax_ids(self):
        # Simulate missing tax_ids field.
        session = self.standard_session.copy()
        customer_details = session["customer_details"].copy()
        customer_details.pop("tax_ids", None)
        session["customer_details"] = customer_details
        payload = build_payload(session, self.config)
        # Should use default VAT code.
        self.assertEqual(payload["client"]["vatCode"], "0000000000000")

    def test_invalid_amount_total(self):
        # Provide a non-numeric amount_total.
        session = self.standard_session.copy()
        session["amount_total"] = "not a number"
        with self.assertRaises(Exception):
            build_payload(session, self.config)

    def test_zero_product_quantity(self):
        # If quantity is not explicitly provided, our function defaults to 1.
        # To simulate an edge case, you could modify build_payload to validate quantity.
        # For now, we simply ensure quantity is always positive.
        payload = build_payload(self.standard_session, self.config)
        quantity = payload["products"][0].get("quantity", 0)
        self.assertGreater(quantity, 0)

    def test_timestamp_conversion(self):
        # Test that an invalid timestamp raises an error.
        session = self.standard_session.copy()
        session["created"] = "invalid_timestamp"
        with self.assertRaises(Exception):
            build_payload(session, self.config)

if __name__ == '__main__':
    unittest.main()
