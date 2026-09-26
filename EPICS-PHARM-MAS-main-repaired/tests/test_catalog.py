import json
from pathlib import Path
import tempfile
import unittest
from pharm.catalog import Catalog, identifier


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "catalog.json"
        self.product = {"generic_name": "SYNTHETIC", "listing_expiration_date": "20251231",
                        "packaging": [{"package_ndc": "01234-5678-9", "description": "Test bottle"}],
                        "openfda": {"upc": ["001234567895"]}}

    def tearDown(self):
        self.temp.cleanup()

    def catalog(self, data=None):
        self.path.write_text(json.dumps(data if data is not None else [self.product]))
        return Catalog(self.path)

    def test_exact_only_and_leading_zero_preserved(self):
        catalog = self.catalog()
        self.assertEqual("01234-5678-9", catalog.lookup("0123456789")["ndc"])
        for scan in ("99012345678999", "123456789", "abc", "", "01234/56789"):
            with self.subTest(scan=scan), self.assertRaises(ValueError):
                catalog.lookup(scan)

    def test_upc_maps_to_exact_package(self):
        catalog = self.catalog()
        self.assertEqual("Test bottle", catalog.lookup("001234567895")["description"])
        self.assertTrue(catalog.matches("001234567895", "01234-5678-9"))

    def test_listing_date_never_used_as_stock_expiration(self):
        self.assertNotIn("expiry_date", self.catalog().lookup("0123456789"))

    def test_multiple_upc_packages_rejected(self):
        self.product["packaging"].append({"package_ndc": "01234-5678-8", "description": "Other bottle"})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.catalog().lookup("001234567895")

    def test_missing_and_malformed_fields_do_not_crash(self):
        for data in ([{}, {"openfda": None, "packaging": None}], [None], {"results": []}, "broken"):
            with self.subTest(data=data):
                self.assertTrue(self.catalog(data).warning)

    def test_missing_file_and_invalid_json(self):
        self.assertTrue(Catalog(self.path).warning)
        self.path.write_text("{broken")
        self.assertTrue(Catalog(self.path).warning)

    def test_no_guessing_zero_padding(self):
        self.assertFalse(self.catalog().matches("123456789", "0123456789"))
        self.assertEqual("00123", identifier("00-123"))

    def test_scan_without_catalog_retains_identifier_for_manual_entry(self):
        fields, notice = Catalog(self.path).loading_details("00123-456\r\n")
        self.assertEqual({"ndc": "00123456"}, fields)
        self.assertIn("manually", notice)

    def test_ambiguous_scan_does_not_choose_a_package(self):
        self.product["packaging"].append({"package_ndc": "01234-5678-8"})
        fields, notice = self.catalog().loading_details("001234567895")
        self.assertEqual({"ndc": "001234567895"}, fields)
        self.assertIn("Ambiguous", notice)

    def test_valid_lookup_supplies_identity_but_not_stock_details(self):
        fields, notice = self.catalog().loading_details("001234567895")
        self.assertEqual("01234-5678-9", fields["ndc"])
        self.assertEqual("SYNTHETIC", fields["generic_name"])
        self.assertNotIn("expiry_date", fields)
        self.assertNotIn("lot", fields)

    def test_unsupported_scan_does_not_become_manual_identifier(self):
        for scan in ("", "]d20100359651029886", "(01)00359651029886", "abc"):
            with self.subTest(scan=scan), self.assertRaises(ValueError):
                self.catalog().loading_details(scan)


if __name__ == "__main__":
    unittest.main()
