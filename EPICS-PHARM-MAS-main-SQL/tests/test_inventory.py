import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from pharm.store import Store, medicine

PRODUCT = dict(generic_name="SYNTHETIC TEST", ndc="01234-5678-9", lot="DEMO-LOT", expiry_date="2099-12-31",
               unit="bottle", description="Synthetic test only", brand_name="Test", labeler_name="Test")


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "inventory.sqlite3"
        self.store = Store(self.path)
        self.store.add_user("admin", "test-password-123", "admin")

    def tearDown(self):
        self.temp.cleanup()

    def load(self, count=4):
        op = self.store.begin("load", 1, count, PRODUCT, "admin")
        self.store.access(op, "admin")
        self.store.finish(op, "admin", closed=True)
        return op

    def test_starts_empty_without_importing_old_json(self):
        self.assertEqual([0] * 4, [c["quantity"] for c in self.store.compartments()])

    def test_password_free_session_works_without_creating_or_changing_accounts(self):
        operator = self.store.start_local_session()
        op = self.store.begin("load", 1, 1, PRODUCT, operator)
        self.store.access(op, operator)
        self.store.finish(op, operator, closed=True)
        self.assertEqual(1, self.store.compartments()[0]["quantity"])
        self.assertEqual("admin", self.store.authenticate("admin", "test-password-123"))
        self.assertIn("local_session_started", [e["action"] for e in self.store.audit()])
        other = Store(self.path)
        with self.assertRaises(ValueError):
            other.begin("manual", 1, 0, {}, operator, "No explicit local session")

    def test_local_session_can_reconcile_previous_named_users_operation(self):
        op = self.store.begin("load", 1, 1, PRODUCT, "admin")
        self.store.access(op, "admin")
        operator = self.store.start_local_session()
        self.store.reconcile(op, 0, operator, "Inspected empty drawer", closed=True)
        self.assertIsNone(self.store.active())

    def test_load_only_commits_after_closure(self):
        op = self.store.begin("load", 1, 4, PRODUCT, "admin")
        self.store.access(op, "admin")
        self.assertEqual(0, self.store.compartments()[0]["quantity"])
        with self.assertRaises(ValueError):
            self.store.finish(op, "admin")
        self.store.finish(op, "admin", closed=True)
        self.assertEqual(4, self.store.compartments()[0]["quantity"])

    def test_invalid_quantities_leave_no_operation(self):
        for count in (None, 0, -1, True, 1.5, "2"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.store.begin("load", 1, count, PRODUCT, "admin")
        self.assertIsNone(self.store.active())

    def test_invalid_compartments(self):
        for number in (None, 0, 5, True, "1", 1.0):
            with self.subTest(number=number), self.assertRaises(ValueError):
                self.store.begin("load", number, 1, PRODUCT, "admin")

    def test_blank_and_expired_product_rejected(self):
        for product in ({}, {**PRODUCT, "expiry_date": "2000-01-01"}, {**PRODUCT, "expiry_date": "20261231"},
                        {**PRODUCT, "lot": ""}, {**PRODUCT, "ndc": "abc"}):
            with self.subTest(product=product), self.assertRaises(ValueError):
                medicine(product)

    def test_topup_identity_and_lot_enforced(self):
        self.load()
        for field, value in (("ndc", "98765"), ("lot", "other"), ("unit", "tablet"),
                             ("expiry_date", "2098-01-01"), ("generic_name", "other")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.store.begin("load", 1, 1, {**PRODUCT, field: value}, "admin")
        self.load(2)
        self.assertEqual(6, self.store.compartments()[0]["quantity"])

    def test_cancel_before_access_preserves_stock(self):
        op = self.store.begin("load", 1, 2, PRODUCT, "admin")
        self.store.cancel(op, "admin", "Cancelled before access")
        self.assertIsNone(self.store.active())
        self.assertEqual(0, self.store.compartments()[0]["quantity"])

    def test_partial_dispense_survives_restart_and_blocks_other_client(self):
        self.load()
        op = self.store.begin("dispense", 1, 3, {}, "admin")
        self.store.access(op, "admin")
        self.store.verify_one(op, "admin")
        self.store.cancel(op, "admin", "Second scan failed")
        other = Store(self.path)
        self.assertEqual(1, other.active()["verified"])
        with self.assertRaises(ValueError):
            other.begin("load", 2, 1, PRODUCT, "admin")
        with self.assertRaises(ValueError):
            other.finish(op, "admin", closed=True)
        other.reconcile(op, 3, "admin", "One bottle removed; counted the remaining bottles", closed=True)
        self.assertEqual(3, self.store.compartments()[0]["quantity"])
        self.assertIsNone(self.store.active())

    def test_duplicate_access_and_commit_rejected(self):
        op = self.store.begin("load", 1, 2, PRODUCT, "admin")
        self.store.access(op, "admin")
        with self.assertRaises(ValueError):
            self.store.access(op, "admin")
        self.store.finish(op, "admin", closed=True)
        with self.assertRaises(ValueError):
            self.store.finish(op, "admin", closed=True)
        self.assertEqual(2, self.store.compartments()[0]["quantity"])

    def test_depletion_clears_product(self):
        self.load(1)
        op = self.store.begin("dispense", 1, 1, {}, "admin")
        self.store.access(op, "admin")
        self.store.verify_one(op, "admin")
        self.store.finish(op, "admin", closed=True)
        self.assertEqual({}, self.store.compartments()[0]["product"])

    def test_insufficient_stock(self):
        self.load(1)
        with self.assertRaises(ValueError):
            self.store.begin("dispense", 1, 2, {}, "admin")

    def test_unload_does_not_erase_before_confirmation(self):
        self.load()
        op = self.store.begin("unload", 1, 0, {}, "admin")
        self.store.access(op, "admin")
        self.assertEqual(4, self.store.compartments()[0]["quantity"])
        self.store.finish(op, "admin", closed=True)
        self.assertEqual(0, self.store.compartments()[0]["quantity"])

    def test_operator_roles_and_passwords(self):
        self.assertEqual("admin", self.store.authenticate("admin", "test-password-123"))
        self.assertIsNone(self.store.authenticate("admin", "wrong"))
        self.store.add_user("staff", "staff-password-123", actor="admin")
        with self.assertRaises(ValueError):
            self.store.begin("load", 1, 2, PRODUCT, "staff")
        with self.assertRaises(ValueError):
            self.store.add_user("extra", "extra-password-123", actor="staff")
        self.load(1)
        op = self.store.begin("dispense", 1, 1, {}, "staff")
        self.store.access(op, "staff")
        self.store.cancel(op, "staff", "Cancelled")
        with self.assertRaises(ValueError):
            self.store.reconcile(op, 1, "staff", "Counted", closed=True)
        self.store.reconcile(op, 1, "admin", "Counted", closed=True)

    def test_manual_requires_reason_and_reconciliation(self):
        with self.assertRaises(ValueError):
            self.store.begin("manual", 1, 0, {}, "admin")
        op = self.store.begin("manual", 1, 0, {}, "admin", "Inspect empty compartment")
        self.store.access(op, "admin")
        with self.assertRaises(ValueError):
            self.store.finish(op, "admin", closed=True)
        with self.assertRaises(ValueError):
            self.store.reconcile(op, 1, "admin", "Unknown stock", closed=True)
        self.store.reconcile(op, 0, "admin", "Empty and secured", closed=True)

    def test_audit_is_append_only(self):
        self.load()
        with self.store.connect() as db:
            for sql in ("DELETE FROM events", "UPDATE events SET detail='changed'"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        self.assertIn("committed", [e["action"] for e in self.store.audit()])

    def test_backup_is_consistent_and_does_not_overwrite(self):
        self.load()
        destination = Path(self.temp.name) / "backup.sqlite3"
        self.store.backup(destination)
        self.assertEqual(self.store.compartments(), Store(destination).compartments())
        with self.assertRaises(ValueError):
            self.store.backup(destination)


if __name__ == "__main__":
    unittest.main()
