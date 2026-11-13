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

    def tearDown(self): self.temp.cleanup()

    def submit(self, atm="ATM-100-1234", code="HW-104", description="card reader broken"):
        return self.client.post("/api/reports", json={"reporter_name":"A. User","reporter_contact":"555-0100","atm_id":atm,"error_code":code,"description":description})

    def test_valid_atm_dfa_and_regex_agree(self):
        x=api.validate_atm_id("ATM-100-1234"); self.assertTrue(x["valid"]); self.assertEqual(x["dfa"],x["regex"])
    def test_invalid_atm_shape(self): self.assertFalse(api.validate_atm_id("100-1234")["valid"])
    def test_unknown_prefix_invalid(self): self.assertFalse(api.validate_atm_id("ATM-999-1234")["valid"])
    def test_malformed_atm_length(self): self.assertFalse(api.validate_atm_id("ATM-100-1")["valid"])
    def test_valid_error_code(self): self.assertTrue(api.validate_error_code("ERR-1234"))
    def test_invalid_error_code(self): self.assertFalse(api.validate_error_code("123-ERR"))
    def test_hardware_classification(self): self.assertEqual(api.classify("printer motor broken"),"Hardware")
    def test_network_classification(self): self.assertEqual(api.classify("ATM offline network timeout"),"Network")
    def test_cash_classification(self): self.assertEqual(api.classify("cash dispenser jam"),"Cash handling")
    def test_software_classification(self): self.assertEqual(api.classify("software application reboot"),"Software")
    def test_security_classification(self): self.assertEqual(api.classify("possible card skimming fraud"),"Security")
    def test_conflict_prefers_security(self): self.assertEqual(api.classify("cash dispenser jam and tamper alert"),"Security")
    def test_unknown_zone_rejected(self): self.assertEqual(self.submit(atm="ATM-999-1234").status_code,400)
    def test_handler_unavailable_queues(self):
        with api.connect() as db: db.execute("UPDATE handlers SET available=0")
        r=self.submit(); self.assertEqual(r.json["status"],"Pending"); self.assertIsNone(r.json["handler"])
    def test_capacity_exceeded_uses_backup(self):
        with api.connect() as db: db.execute("UPDATE handlers SET capacity=1 WHERE zone='North'"); db.execute("UPDATE handlers SET available=0 WHERE zone!='North'")
        self.assertEqual(self.submit().json["status"],"Assigned")
        result=self.submit(); self.assertIsNone(result.json["handler"]); self.assertEqual(result.json["status"],"Pending")
    def test_backup_handler_assignment(self):
        with api.connect() as db: db.execute("UPDATE handlers SET available=0 WHERE zone='North'")
        r=self.submit(); self.assertIsNotNone(r.json["handler"]); self.assertIn("backup",r.json["escalation"])
    def test_emergency_override(self): self.assertIn("Critical",self.submit(description="security fraud alert").json["escalation"])
    def test_priority_queue_order(self):
        self.submit(description="hardware issue"); critical=self.submit(description="security fraud alert")
        self.assertEqual(self.client.get("/api/reports").json[0]["id"],critical.json["id"])
    def test_duplicate_report_ids_prevented(self):
        a=self.submit().json["id"]
        with api.connect() as db:
            row=db.execute("SELECT * FROM reports WHERE id=?",(a,)).fetchone()
            cols=[row[k] for k in row.keys()]
            with self.assertRaises(Exception): db.execute("INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",cols)
    def test_submission_persists(self):
        r=self.submit(); self.assertEqual(self.client.get("/api/reports/"+r.json["id"]).status_code,200)
    def test_status_update_persists(self):
        rid=self.submit().json["id"]; self.client.patch(f"/api/reports/{rid}/status",json={"status":"In Progress"})
        self.assertEqual(self.client.get(f"/api/reports/{rid}").json["status"],"In Progress")
    def test_report_id_search(self):
        rid=self.submit().json["id"]; self.assertEqual(self.client.get(f"/api/reports/{rid}").json["id"],rid)
    def test_analytics_count_accuracy(self):
        self.submit(); self.submit(atm="ATM-200-0200",description="network offline")
        self.assertEqual(self.client.get("/api/analytics").json["total"],2)
    def test_end_to_end_workflow(self):
        r=self.submit(description="ATM offline network timeout"); self.assertEqual(r.json["category"],"Network")
        self.client.patch(f"/api/reports/{r.json['id']}/status",json={"status":"Resolved"})
        self.assertEqual(self.client.get("/api/analytics").json["resolved"],1)
    def test_invalid_status_rejected(self):
        rid=self.submit().json["id"]; self.assertEqual(self.client.patch(f"/api/reports/{rid}/status",json={"status":"Closed"}).status_code,400)

if __name__ == "__main__": unittest.main()
