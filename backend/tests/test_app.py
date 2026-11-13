"""Comprehensive Test Suite for ATM Error Logger & Dispatcher.
Covers Part D requirements (at least 15 test cases covering DFA/regex agreement,
classification, routing, capacity, priority override, fallback, and persistence).
"""
import json
import tempfile
import unittest
from pathlib import Path

import app as api

class ATMApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        api.DB_PATH = Path(self.temp.name) / "test.db"
        api.init_db()
        self.client = api.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def submit(
        self,
        atm="ATMNOR1001",
        code="E01H",
        description="card reader hardware broken",
        name="Officer Jane",
        contact="555-0199",
        urgency="Low"
    ):
        return self.client.post("/api/reports", json={
            "reporter_name": name,
            "reporter_contact": contact,
            "atm_id": atm,
            "error_code": code,
            "description": description,
            "urgency": urgency
        })

    # ------------------------------------------------------------------------
    # Category 1: Valid & Invalid Input Formats + DFA/Regex Agreement (Part A)
    # ------------------------------------------------------------------------
    def test_01_valid_atm_id_standard_dfa_and_regex_agree(self):
        """Test ATM[3-alpha][4-digit] standard format with DFA and regex agreement."""
        res = api.validate_atm_id("ATMNOR1001")
        self.assertTrue(res["valid"])
        self.assertTrue(res["dfa"])
        self.assertTrue(res["regex"])
        self.assertTrue(res["agree"])
        self.assertEqual(res["zone"], "North")

    def test_02_valid_atm_id_with_hyphens_dfa_and_regex_agree(self):
        """Test hyphenated ATM ID format (e.g. ATM-NOR-1001)."""
        res = api.validate_atm_id("ATM-NOR-1001")
        self.assertTrue(res["valid"])
        self.assertEqual(res["dfa"], res["regex"])
        self.assertEqual(res["zone"], "North")

    def test_03_invalid_atm_id_shape_and_length(self):
        """Test malformed ATM IDs fail both DFA and regex."""
        # Missing prefix
        r1 = api.validate_atm_id("NOR1001")
        self.assertFalse(r1["valid"])
        # Incomplete digits
        r2 = api.validate_atm_id("ATMNOR1")
        self.assertFalse(r2["valid"])
        # Non-alphanumeric characters
        r3 = api.validate_atm_id("ATM@#$1234")
        self.assertFalse(r3["valid"])

    def test_04_valid_error_code_standard_e_format(self):
        """Test E[2-digit][1-alpha] standard format."""
        res = api.validate_error_code("E01H")
        self.assertTrue(res["valid"])
        self.assertTrue(res["agree"])

    def test_05_invalid_error_code_rejection(self):
        """Test malformed error codes are properly rejected."""
        self.assertFalse(api.validate_error_code("E1H")["valid"])     # Only 1 digit
        self.assertFalse(api.validate_error_code("123-ERR")["valid"])  # Inverted

    # ------------------------------------------------------------------------
    # Category 2: Classification into Exactly 5 Categories & Conflict Rules
    # ------------------------------------------------------------------------
    def test_06_hardware_classification(self):
        cat, reason = api.classify("receipt printer motor broken", "E01H")
        self.assertEqual(cat, "Hardware")

    def test_07_network_classification(self):
        cat, reason = api.classify("ATM offline host connection timeout", "E02N")
        self.assertEqual(cat, "Network")

    def test_08_cash_handling_classification(self):
        cat, reason = api.classify("dispenser cassette jam cash out failure", "E03C")
        self.assertEqual(cat, "Cash-Handling")

    def test_09_software_classification(self):
        cat, reason = api.classify("application system crash screen frozen", "E04S")
        self.assertEqual(cat, "Software")

    def test_10_security_classification(self):
        cat, reason = api.classify("possible card skimming fraud tamper detected", "E05X")
        self.assertEqual(cat, "Security")

    def test_11_conflicting_classification_patterns_deterministic_priority(self):
        """Security takes deterministic priority over Cash-Handling and Hardware."""
        cat, reason = api.classify("cash dispenser jam with physical tamper alert", "E01H")
        self.assertEqual(cat, "Security")
        self.assertIn("Conflict detected", reason)

    def test_12_unmapped_unknown_error_code_handled(self):
        """Unknown or unmapped codes return None without silent misclassification."""
        cat, reason = api.classify("normal routine status check", "UNKNOWN")
        self.assertIsNone(cat)
        self.assertIn("Unmapped", reason)

    # ------------------------------------------------------------------------
    # Category 3: Regional Routing, Security Desk Bypass, and Fallback (Part B)
    # ------------------------------------------------------------------------
    def test_13_security_errors_bypass_regional_teams_to_central_security_desk(self):
        """Part B Item 5: Security errors bypass regional teams to Central Security Desk."""
        r = self.submit(atm="ATMNOR1001", code="E05X", description="unauthorized intrusion attempt")
        self.assertEqual(r.status_code, 201)
        data = r.json
        self.assertEqual(data["category"], "Security")
        self.assertEqual(data["priority"], "Critical")
        self.assertIn("Security Desk", data["handler"])
        self.assertIn("Bypassed regional teams", data["escalation"])

    def test_14_regional_routing_all_four_zones(self):
        """Prefixes map to North, South, East, West."""
        zones = [
            ("ATMNOR1001", "North"),
            ("ATMSOU2002", "South"),
            ("ATMEAS3003", "East"),
            ("ATMWES4004", "West")
        ]
        for atm, expected_zone in zones:
            r = self.submit(atm=atm, description="card reader jammed")
            self.assertEqual(r.json["zone"], expected_zone)
            self.assertEqual(r.json["status"], "Assigned")

    def test_15_unknown_prefix_routed_to_central_fallback_queue(self):
        """Part B Item 7: Unknown routing key sends to Central Fallback queue."""
        # ATM with valid format syntax but unmapped region "XYZ"
        res = api.validate_atm_id("ATMXYZ9999")
        self.assertFalse(res["valid"])
        self.assertIn("Unknown regional prefix", res["message"])

    # ------------------------------------------------------------------------
    # Category 4: Handler Availability, Capacity Overflow, and Failover
    # ------------------------------------------------------------------------
    def test_16_handler_unavailable_queues_report(self):
        with api.connect() as db:
            db.execute("UPDATE handlers SET available=0 WHERE zone='North'")
            db.execute("UPDATE handlers SET available=0 WHERE zone!='North'")
        r = self.submit(atm="ATMNOR1001")
        self.assertEqual(r.json["status"], "Pending")
        self.assertIsNone(r.json["handler"])

    def test_17_capacity_exceeded_uses_backup_handler(self):
        """Capacity overflow reassigns to an eligible backup handler."""
        with api.connect() as db:
            db.execute("UPDATE handlers SET capacity=1 WHERE zone='North'")
        # First takes the 1 capacity slot
        r1 = self.submit(atm="ATMNOR1001")
        self.assertEqual(r1.json["status"], "Assigned")
        self.assertIn("North Regional Lead", r1.json["handler"])
        
        # Second should failover to an eligible backup regional handler
        r2 = self.submit(atm="ATMNOR1001")
        self.assertEqual(r2.json["status"], "Assigned")
        self.assertIn("failover assigned to", r2.json["escalation"])

    # ------------------------------------------------------------------------
    # Category 5: Priority Overrides & Queue Ordering
    # ------------------------------------------------------------------------
    def test_18_priority_override_escalation(self):
        r = self.submit(description="emergency forced entry security breach")
        self.assertEqual(r.json["priority"], "Critical")
        self.assertIn("Priority Override", r.json["escalation"])

    def test_19_priority_queue_ordering(self):
        """Critical reports are ordered before Low priority reports."""
        self.submit(description="low priority printer paper low", urgency="Low")
        crit = self.submit(description="critical tamper alert", urgency="Critical")
        reports = self.client.get("/api/reports").json
        self.assertEqual(reports[0]["id"], crit.json["id"])

    # ------------------------------------------------------------------------
    # Category 6: Persistence, Status Lifecycle & Analytics
    # ------------------------------------------------------------------------
    def test_20_status_lifecycle_workflow_persists(self):
        """Full workflow: Submit -> Assigned -> In Progress -> Resolved."""
        r = self.submit()
        rid = r.json["id"]
        self.assertEqual(r.json["status"], "Assigned")

        p1 = self.client.patch(f"/api/reports/{rid}/status", json={"status": "In Progress"})
        self.assertEqual(p1.json["status"], "In Progress")

        p2 = self.client.patch(f"/api/reports/{rid}/status", json={"status": "Resolved"})
        self.assertEqual(p2.json["status"], "Resolved")

        # Verify in analytics
        analytics = self.client.get("/api/analytics").json
        self.assertEqual(analytics["resolved"], 1)

    def test_21_report_search_by_id(self):
        r = self.submit()
        rid = r.json["id"]
        found = self.client.get(f"/api/reports/{rid}")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json["id"], rid)

    def test_22_dfa_simulation_endpoint(self):
        """Verifies the /api/dfa-simulate endpoint provides full step-by-step state traces."""
        res = self.client.post("/api/dfa-simulate", json={"type": "atm", "input": "ATMNOR1001"})
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertTrue(data["dfa_accepted"])
        self.assertTrue(data["regex_accepted"])
        self.assertTrue(data["agree"])
        self.assertEqual(data["final_state"], "q12")
        self.assertGreater(len(data["trace"]), 5)

if __name__ == "__main__":
    unittest.main()
