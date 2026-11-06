import json
from pathlib import Path
import tempfile
import unittest
from pharm.catalog import Catalog, identifier, unit_type


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
        self.assertEqual({"ndc": "001234567895", "generic_name": "SYNTHETIC"}, fields)
        self.assertIn("Ambiguous", notice)

    def test_ambiguous_scan_fills_only_what_every_package_shares(self):
        self.product["packaging"] = [{"package_ndc": f"01234-5678-{n}", "description": f"{n}0 TABLET in 1 BOTTLE (01234-5678-{n})"}
                                     for n in (8, 9)]
        fields, notice = self.catalog().loading_details("001234567895")
        self.assertEqual({"ndc": "001234567895", "generic_name": "SYNTHETIC", "unit": "bottle"}, fields)
        self.assertIn("check them against the label", notice)
        other = {"generic_name": "OTHER", "packaging": [{"package_ndc": "05555-111-22"}], "openfda": {"upc": ["001234567895"]}}
        fields, _ = self.catalog([self.product, other]).loading_details("001234567895")
        self.assertEqual({"ndc": "001234567895"}, fields)

    def test_drug_barcode_carries_the_package_ndc_without_a_listed_upc(self):
        del self.product["openfda"]
        catalog = self.catalog()
        for scan in ("301234567896", "0301234567896", "00301234567896", "(01)00301234567896(17)991231(10)LOT"):
            with self.subTest(scan=scan):
                self.assertEqual("01234-5678-9", catalog.lookup(scan)["ndc"])
                self.assertTrue(catalog.matches(scan, "01234-5678-9"))
        # Wrong check digit; case-level packaging indicator.
        for scan in ("301234567897", "10301234567893"):
            with self.subTest(scan=scan), self.assertRaises(ValueError):
                catalog.lookup(scan)

    def test_drug_barcode_ndc_wins_over_a_relabelers_copied_upc(self):
        relabeler = {"generic_name": "SYNTHETIC", "labeler_name": "Relabeler",
                     "packaging": [{"package_ndc": "99999-111-22"}], "openfda": {"upc": ["0301234567896"]}}
        self.assertEqual("01234-5678-9", self.catalog([self.product, relabeler]).lookup("301234567896")["ndc"])

    def test_upc_listed_as_ean13_matches_upc_a_and_gs1_scans(self):
        self.product["openfda"]["upc"] = ["0001234567895"]
        catalog = self.catalog()
        for scan in ("001234567895", "(01)00001234567895"):
            with self.subTest(scan=scan):
                self.assertEqual("01234-5678-9", catalog.lookup(scan)["ndc"])

    def test_found_package_fills_medication_and_unit_type(self):
        self.product["packaging"][0]["description"] = "100 TABLET in 1 BOTTLE, PLASTIC (01234-5678-9)"
        fields, notice = self.catalog().loading_details("(01)00301234567896(17)991231(10)LOT")
        self.assertEqual(("SYNTHETIC", "bottle", "01234-5678-9", "LOT", "2099-12-31"),
                         tuple(fields[k] for k in ("generic_name", "unit", "ndc", "lot", "expiry_date")))
        self.assertIn("Package found", notice)

    def test_unlisted_package_of_a_listed_product_fills_medication(self):
        self.product["packaging"][0]["description"] = "100 TABLET in 1 BOTTLE (01234-5678-9)"
        # The drug barcode carries 01234-5678-0, a package size missing from the catalog.
        fields, notice = self.catalog().loading_details("301234567803")
        self.assertEqual({"ndc": "301234567803", "generic_name": "SYNTHETIC", "unit": "bottle"}, fields)
        self.assertIn("No exact package match", notice)

    def test_unit_type_is_the_outer_container(self):
        for description, unit in (("100 TABLET, FILM COATED in 1 BOTTLE, PLASTIC (0406-0512-01)", "bottle"),
                                  ("1 INHALER in 1 CARTON (0173-0682-24)  / 60 AEROSOL, METERED in 1 INHALER", "carton"),
                                  ("10 POUCH in 1 BOX (1-2-3) * 1 PATCH in 1 POUCH", "box"),
                                  ("28 TABLET in 1 BLISTER PACK (1-2-3)", "blister pack"),
                                  ("1 mL in 1 VIAL, SINGLE-DOSE (1-2-3)", "vial"),
                                  ("1 KIT in 1 NOT APPLICABLE (1-2-3)", ""), ("Test bottle", ""), ("", "")):
            with self.subTest(description=description):
                self.assertEqual(unit, unit_type(description))

    def test_valid_lookup_supplies_identity_but_not_stock_details(self):
        fields, notice = self.catalog().loading_details("001234567895")
        self.assertEqual("01234-5678-9", fields["ndc"])
        self.assertEqual("SYNTHETIC", fields["generic_name"])
        self.assertNotIn("expiry_date", fields)
        self.assertNotIn("lot", fields)

    def test_unsupported_scan_does_not_become_manual_identifier(self):
        for scan in ("", "]d2010035", "(01)0035", "abc"):
            with self.subTest(scan=scan), self.assertRaises(ValueError):
                self.catalog().loading_details(scan)


if __name__ == "__main__":
    unittest.main()
