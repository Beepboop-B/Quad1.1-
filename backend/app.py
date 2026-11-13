"""ATM Error Logger API. Business rules and persistence live in this module."""
from __future__ import annotations

import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ATM_DB_PATH", ROOT / "atm_errors.db"))
ZONES = {"100": "North", "200": "South", "300": "East", "400": "West"}
DEFAULT_HANDLERS = [("North", "Nora Singh"), ("South", "Samir Rao"), ("East", "Esha Das"), ("West", "Wesley Chen")]
ERROR_RE = re.compile(r"^[A-Z]{2,4}-\d{3,5}$")
ATM_RE = re.compile(r"^ATM-(100|200|300|400)-\d{3,5}$")

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class ClosingConnection(sqlite3.Connection):
    """SQLite's context manager commits but does not close; close after each unit of work."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()

def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS handlers (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, zone TEXT NOT NULL UNIQUE,
          available INTEGER NOT NULL DEFAULT 1, capacity INTEGER NOT NULL DEFAULT 8
        );
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, reporter_name TEXT NOT NULL, reporter_contact TEXT NOT NULL,
          atm_id TEXT NOT NULL, error_code TEXT NOT NULL, description TEXT NOT NULL,
          category TEXT NOT NULL, priority TEXT NOT NULL, zone TEXT NOT NULL,
          status TEXT NOT NULL, handler_id INTEGER REFERENCES handlers(id),
          backup_handler_id INTEGER REFERENCES handlers(id), escalation TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS reports_atm ON reports(atm_id);
        CREATE INDEX IF NOT EXISTS reports_status ON reports(status);
        """)
        for zone, name in DEFAULT_HANDLERS:
            db.execute("INSERT OR IGNORE INTO handlers(name,zone) VALUES (?,?)", (name, zone))

def validate_atm_id(value: str) -> dict[str, Any]:
    dfa = bool(value and ATM_RE.fullmatch(value))
    regex = bool(value and re.fullmatch(r"ATM-\d{3}-\d{3,5}", value) and value[4:7] in ZONES)
    zone = ZONES.get(value[4:7]) if dfa else None
    return {"valid": dfa and regex, "dfa": dfa, "regex": regex, "zone": zone,
            "message": "ATM ID is valid." if dfa and regex else "Use ATM-100-1234 with a supported zone prefix (100, 200, 300, 400)."}

def validate_error_code(value: str) -> bool:
    return bool(value and ERROR_RE.fullmatch(value))

def classify(description: str, error_code: str = "") -> str:
    text = f"{description} {error_code}".lower()
    code = error_code.upper().split("-", 1)[0]
    code_categories = {"HW": "Hardware", "HARD": "Hardware", "NW": "Network", "NET": "Network",
                       "CH": "Cash handling", "CASH": "Cash handling", "SW": "Software", "SOFT": "Software",
                       "SEC": "Security", "SE": "Security"}
    patterns = {
        "Security": ("fraud", "skimming", "tamper", "unauthorized", "security", "intrusion", "forced"),
        "Cash handling": ("cash", "dispenser", "jam", "currency", "cassette", "retract", "cash-out"),
        "Network": ("network", "offline", "connection", "connectivity", "timeout", "host", "通信"),
        "Software": ("software", "application", "firmware", "screen", "reboot", "system", "error"),
        "Hardware": ("hardware", "card reader", "printer", "keypad", "sensor", "motor", "broken"),
    }
    # Specific safety and cash signals take precedence when descriptions conflict.
    for category in ("Security", "Cash handling", "Network", "Software", "Hardware"):
        if any(word in text for word in patterns[category]):
            return category
    return code_categories.get(code, "Hardware")

def priority_for(description: str, error_code: str = "") -> str:
    text = f"{description} {error_code}".lower()
    if any(x in text for x in ("fraud", "skimming", "tamper", "security", "forced", "emergency")):
        return "Critical"
    if any(x in text for x in ("cash-out", "all atm", "branch down", "dispenser jam", "offline", "urgent")):
        return "High"
    if any(x in text for x in ("degraded", "intermittent", "slow")):
        return "Medium"
    return "Low"

def report_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["handler"] = data.pop("handler_name", None)
    data["backup_handler"] = data.pop("backup_name", None)
    data["available"] = None
    return data

def report_query(db: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict[str, Any]]:
    rows = db.execute(f"""SELECT r.*, h.name handler_name, b.name backup_name
      FROM reports r LEFT JOIN handlers h ON r.handler_id=h.id
      LEFT JOIN handlers b ON r.backup_handler_id=b.id {where}
      ORDER BY CASE r.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, r.created_at DESC""", params).fetchall()
    return [report_dict(row) for row in rows]

def assign(db: sqlite3.Connection, zone: str, priority: str) -> tuple[int | None, int | None, str | None]:
    loads = db.execute("SELECT h.*, (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') load FROM handlers h ORDER BY h.id").fetchall()
    local = [h for h in loads if h["zone"] == zone]
    eligible = [h for h in local if h["available"] and h["load"] < h["capacity"]]
    chosen = min(eligible, key=lambda h: h["load"]) if eligible else None
    other = [h for h in loads if h["zone"] != zone and h["available"] and h["load"] < h["capacity"]]
    backup = min(other, key=lambda h: h["load"]) if other else None
    escalation = None
    if priority == "Critical":
        escalation = "Critical priority override: regional on-call escalation notified."
    if chosen:
        return chosen["id"], backup["id"] if backup else None, escalation
    if backup:
        escalation = (escalation + " " if escalation else "") + f"Regional capacity exceeded; reassigned to {backup['zone']} backup."
        return backup["id"], None, escalation
    escalation = (escalation + " " if escalation else "") + "No available handler; report queued for dispatch."
    return None, None, escalation

app = Flask(__name__)
CORS(app)
init_db()

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "database": str(DB_PATH)})

@app.post("/api/validate")
def validate():
    body = request.get_json(silent=True) or {}
    atm = validate_atm_id(str(body.get("atm_id", "")).strip().upper())
    code = str(body.get("error_code", "")).strip().upper()
    description = str(body.get("description", "")).strip()
    return jsonify({"atm": atm, "error_code_valid": validate_error_code(code),
                    "category": classify(description, code) if description else None,
                    "priority": priority_for(description, code) if description else None})

@app.get("/api/reports")
def reports():
    with connect() as db:
        return jsonify(report_query(db))

@app.post("/api/reports")
def create_report():
    body = request.get_json(silent=True) or {}
    name, contact = str(body.get("reporter_name", "")).strip(), str(body.get("reporter_contact", "")).strip()
    atm = str(body.get("atm_id", "")).strip().upper()
    code = str(body.get("error_code", "")).strip().upper()
    description = str(body.get("description", "")).strip()
    errors = {}
    if not name: errors["reporter_name"] = "Enter your name."
    if not contact: errors["reporter_contact"] = "Enter a contact detail."
    validation = validate_atm_id(atm)
    if not validation["valid"]: errors["atm_id"] = validation["message"]
    if not validate_error_code(code): errors["error_code"] = "Use 2–4 letters, a hyphen, then 3–5 digits (for example HW-104)."
    if len(description) < 5: errors["description"] = "Describe the issue in at least 5 characters."
    if errors: return jsonify({"error": "Please correct the highlighted fields.", "fields": errors}), 400
    category, priority, zone = classify(description, code), priority_for(description, code), validation["zone"]
    rid, created = f"ATM-{uuid.uuid4().hex.upper()}", now()
    try:
        with connect() as db:
            handler, backup, escalation = assign(db, zone, priority)
            status = "Assigned" if handler else "Pending"
            db.execute("""INSERT INTO reports(id,reporter_name,reporter_contact,atm_id,error_code,description,category,priority,zone,status,handler_id,backup_handler_id,escalation,created_at,updated_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (rid,name,contact,atm,code,description,category,priority,zone,status,handler,backup,escalation,created,created))
            result = report_query(db, "WHERE r.id=?", (rid,))[0]
        return jsonify(result), 201
    except sqlite3.Error as exc:
        return jsonify({"error": f"Could not save report: {exc}"}), 500

@app.get("/api/reports/<report_id>")
def get_report(report_id: str):
    with connect() as db:
        found = report_query(db, "WHERE r.id=?", (report_id.upper(),))
    if not found: return jsonify({"error": "No report found with that ID."}), 404
    return jsonify(found[0])

@app.patch("/api/reports/<report_id>/status")
def update_status(report_id: str):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in ("Pending", "Assigned", "In Progress", "Resolved"):
        return jsonify({"error": "Status must be Pending, Assigned, In Progress, or Resolved."}), 400
    with connect() as db:
        row = db.execute("SELECT * FROM reports WHERE id=?", (report_id.upper(),)).fetchone()
        if not row: return jsonify({"error": "No report found with that ID."}), 404
        db.execute("UPDATE reports SET status=?,updated_at=? WHERE id=?", (status,now(),report_id.upper()))
        return jsonify(report_query(db, "WHERE r.id=?", (report_id.upper(),))[0])

@app.get("/api/handlers")
def handlers():
    with connect() as db:
        rows = db.execute("""SELECT h.*, (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') load FROM handlers h ORDER BY h.zone""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.patch("/api/handlers/<int:handler_id>")
def update_handler(handler_id: int):
    body = request.get_json(silent=True) or {}
    with connect() as db:
        row = db.execute("SELECT * FROM handlers WHERE id=?", (handler_id,)).fetchone()
        if not row: return jsonify({"error":"Handler not found."}),404
        available = body.get("available", row["available"])
        capacity = body.get("capacity", row["capacity"])
        try: capacity=int(capacity)
        except (ValueError,TypeError): return jsonify({"error":"Capacity must be a positive integer."}),400
        if capacity < 1: return jsonify({"error":"Capacity must be a positive integer."}),400
        db.execute("UPDATE handlers SET available=?,capacity=? WHERE id=?", (int(bool(available)),capacity,handler_id))
        return jsonify(dict(db.execute("SELECT h.*, (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') load FROM handlers h WHERE id=?",(handler_id,)).fetchone()))

@app.get("/api/routing")
def routing():
    with connect() as db:
        hs = [dict(r) for r in db.execute("SELECT h.*, (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') load FROM handlers h ORDER BY h.zone")]
        rs = report_query(db)
    return jsonify({"mappings":[{"prefix":k,"zone":v,"handler":next((h["name"] for h in hs if h["zone"]==v),None)} for k,v in ZONES.items()],"handlers":hs,"reports":rs,"queued":[r for r in rs if r["status"]=="Pending" and not r["handler"]]})

@app.get("/api/analytics")
def analytics():
    with connect() as db:
        total=db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        def grouped(field: str):
            return [dict(r) for r in db.execute(f"SELECT {field} name,COUNT(*) value FROM reports GROUP BY {field} ORDER BY {field}")]
        statuses={r["name"]:r["value"] for r in grouped("status")}
        return jsonify({"total":total,"pending":statuses.get("Pending",0),"assigned":statuses.get("Assigned",0),"in_progress":statuses.get("In Progress",0),"resolved":statuses.get("Resolved",0),"zones":grouped("zone"),"categories":grouped("category"),"priorities":grouped("priority"),"statuses":grouped("status"),"daily":[dict(r) for r in db.execute("SELECT substr(created_at,1,10) name,COUNT(*) value FROM reports GROUP BY name ORDER BY name DESC LIMIT 14")]})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
