"""Tests for backend/countries.py (country derivation from location text)."""
import unittest

from backend.countries import derive_country


class DeriveCountryTests(unittest.TestCase):
    def test_plain_country_names(self):
        self.assertEqual(derive_country("Germany"), "Germany")
        self.assertEqual(derive_country("Canada"), "Canada")
        self.assertEqual(derive_country("Brazil"), "Brazil")
        self.assertEqual(derive_country("India"), "India")

    def test_country_in_longer_location(self):
        self.assertEqual(
            derive_country("Corby, England, United Kingdom"), "United Kingdom"
        )
        self.assertEqual(
            derive_country("Kochi, Kerala, India"), "India"
        )
        self.assertEqual(
            derive_country("Chatswood, New South Wales, Australia"), "Australia"
        )

    def test_aliases(self):
        self.assertEqual(derive_country("USA"), "United States")
        self.assertEqual(derive_country("Remote - US only"), "United States")
        self.assertEqual(derive_country("Dubai, UAE"), "United Arab Emirates")

    def test_new_south_wales_is_australia_not_uk(self):
        self.assertEqual(derive_country("New South Wales"), "Australia")

    def test_no_country_returns_empty(self):
        self.assertEqual(derive_country("Remote"), "")
        self.assertEqual(derive_country("Worldwide"), "")
        self.assertEqual(derive_country(""), "")

    def test_region_not_confused_with_country(self):
        # "Northern America" / "LATAM" are regions, not the United States.
        self.assertEqual(derive_country("Northern America, LATAM, Europe, APAC"), "")


if __name__ == "__main__":
    unittest.main()
