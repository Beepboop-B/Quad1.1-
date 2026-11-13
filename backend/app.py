"""ATM Error Logger & Dispatcher API.
Integrates BCS503 (Automata Theory & Computability - DFA & Regex)
and BCS502 (Computer Networks - Routing Table, Dispatch & Escalation).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ATM_DB_PATH", ROOT / "atm_errors.db"))

# ============================================================================
# BCS503: AUTOMATA THEORY & COMPUTABILITY - FORMAL DFA SIMULATOR & REGEX
# ============================================================================

class DFA:
    """Formal Deterministic Finite Automaton (Q, Sigma, delta, q0, F)."""
    def __init__(
        self,
        name: str,
        states: Set[str],
        alphabet_desc: str,
        transitions: Dict[Tuple[str, str], str],
        start_state: str,
        accept_states: Set[str],
        predicate_transitions: Optional[List[Tuple[str, Any, str]]] = None,
    ):
        self.name = name
        self.states = states
        self.alphabet_desc = alphabet_desc
        self.transitions = transitions
        self.start_state = start_state
        self.accept_states = accept_states
        self.predicate_transitions = predicate_transitions or []

    def transition(self, current_state: str, char: str) -> str:
        # 1. Exact character transition
        if (current_state, char) in self.transitions:
            return self.transitions[(current_state, char)]
        # 2. Predicate-based transitions (e.g. isalpha, isdigit)
        for state, predicate, next_state in self.predicate_transitions:
            if state == current_state and predicate(char):
                return next_state
        return "REJECT"

    def simulate(self, input_string: str) -> Dict[str, Any]:
        """Simulates the input string through the DFA, tracking state path."""
        current_state = self.start_state
        trace = [{"step": 0, "char": "START", "state": current_state}]
        
        for idx, ch in enumerate(input_string):
            next_state = self.transition(current_state, ch)
            trace.append({
                "step": idx + 1,
                "char": ch,
                "from_state": current_state,
                "state": next_state,
            })
            current_state = next_state
            if current_state == "REJECT":
                break

        accepted = current_state in self.accept_states
        return {
            "accepted": accepted,
            "final_state": current_state,
            "trace": trace,
            "input_length": len(input_string),
        }


# ----------------------------------------------------------------------------
# DFA 1: ATM ID Validator (ATM[3-alpha][4-digit])
# Formal Language: L = { "ATM" + [A-Z]{3} + [0-9]{4} }, with optional hyphens.
# ----------------------------------------------------------------------------
def _build_atm_dfa() -> DFA:
    states = {f"q{i}" for i in range(13)} | {"REJECT"}
    accept = {"q12"}
    exact: Dict[Tuple[str, str], str] = {
        ("q0", "A"): "q1",
        ("q1", "T"): "q2",
        ("q2", "M"): "q3",
        ("q3", "-"): "q4",
        ("q7", "-"): "q8",
    }
    preds = [
        # q3 or q4: first alpha
        ("q3", lambda c: c.isalpha(), "q5"),
        ("q4", lambda c: c.isalpha(), "q5"),
        # q5: second alpha
        ("q5", lambda c: c.isalpha(), "q6"),
        # q6: third alpha
        ("q6", lambda c: c.isalpha(), "q7"),
        # q7 or q8: first digit
        ("q7", lambda c: c.isdigit(), "q9"),
        ("q8", lambda c: c.isdigit(), "q9"),
        # q9: second digit
        ("q9", lambda c: c.isdigit(), "q10"),
        # q10: third digit
        ("q10", lambda c: c.isdigit(), "q11"),
        # q11: fourth digit -> accept state q12
        ("q11", lambda c: c.isdigit(), "q12"),
    ]
    # Also support backwards-compatible numeric prefix (100, 200, 300, 400)
    for digit in "1234":
        exact[("q3", digit)] = "q5"
        exact[("q4", digit)] = "q5"
    preds.extend([
        ("q5", lambda c: c.isdigit(), "q6"),
        ("q6", lambda c: c.isdigit(), "q7"),
    ])
    return DFA("ATM_ID_DFA", states, "Alphabet: A-Z, 0-9, '-'", exact, "q0", accept, preds)


# ----------------------------------------------------------------------------
# DFA 2: Error Code Validator (E[2-digit][1-alpha])
# Formal Language: L = { "E" + [0-9]{2} + [A-Z] }, with optional hyphens.
# ----------------------------------------------------------------------------
def _build_error_code_dfa() -> DFA:
    states = {f"s{i}" for i in range(7)} | {"REJECT"}
    accept = {"s6"}
    exact: Dict[Tuple[str, str], str] = {
        ("s0", "E"): "s1",
        ("s1", "-"): "s2",
        ("s4", "-"): "s5",
    }
    preds = [
        # s1 or s2: first digit
        ("s1", lambda c: c.isdigit(), "s3"),
        ("s2", lambda c: c.isdigit(), "s3"),
        # s3: second digit
        ("s3", lambda c: c.isdigit(), "s4"),
        # s4 or s5: one alpha -> accept state s6
        ("s4", lambda c: c.isalpha(), "s6"),
        ("s5", lambda c: c.isalpha(), "s6"),
    ]
    return DFA("ERROR_CODE_DFA", states, "Alphabet: E, 0-9, A-Z, '-'", exact, "s0", accept, preds)


ATM_DFA = _build_atm_dfa()
ERROR_CODE_DFA = _build_error_code_dfa()

# Equivalent Regular Expressions
ATM_REGEX = re.compile(r"^ATM-?([A-Z]{3}|\d{3})-?\d{4}$", re.IGNORECASE)
ERROR_CODE_REGEX = re.compile(r"^E-?\d{2}-?[A-Z]$", re.IGNORECASE)
# Backwards-compatibility for legacy codes like HW-104
LEGACY_ERROR_REGEX = re.compile(r"^[A-Z]{2,4}-\d{3,5}$", re.IGNORECASE)


# ============================================================================
# BCS502: COMPUTER NETWORKS - ROUTING TABLE, ZONES & ESCALATION
# ============================================================================

# Regional mappings: Prefix -> Zone
PREFIX_TO_ZONE = {
    # 3-alpha standard prefixes
    "NOR": "North",
    "SOU": "South",
    "EAS": "East",
    "WES": "West",
    # Numeric aliases
    "100": "North",
    "200": "South",
    "300": "East",
    "400": "West",
}

# The 5 Predefined Categories in Part A
CATEGORIES = ["Hardware", "Network", "Cash-Handling", "Software", "Security"]

# Deterministic priority rule when multiple classification patterns match:
# Security > Cash-Handling > Network > Software > Hardware
CATEGORY_PRIORITY_ORDER = ["Security", "Cash-Handling", "Network", "Software", "Hardware"]

CATEGORY_KEYWORDS = {
    "Security": ("fraud", "skimming", "tamper", "unauthorized", "security", "intrusion", "forced", "stolen", "breach"),
    "Cash-Handling": ("cash", "dispenser", "jam", "currency", "cassette", "retract", "cash-out", "reject bin", "bill"),
    "Network": ("network", "offline", "connection", "connectivity", "timeout", "host", "latency", "packet", "dns", "gateway"),
    "Software": ("software", "application", "firmware", "screen", "reboot", "system", "crash", "os", "frozen", "ui"),
    "Hardware": ("hardware", "card reader", "printer", "keypad", "sensor", "motor", "broken", "fan", "receipt"),
}

# Code mappings for E[2-digit][1-alpha] and legacy codes
CODE_CATEGORY_MAP = {
    "H": "Hardware",
    "N": "Network",
    "C": "Cash-Handling",
    "S": "Software",
    "X": "Security",
    "HW": "Hardware",
    "HARD": "Hardware",
    "NW": "Network",
    "NET": "Network",
    "CH": "Cash-Handling",
    "CASH": "Cash-Handling",
    "SW": "Software",
    "SOFT": "Software",
    "SEC": "Security",
    "SE": "Security",
}

DEFAULT_HANDLERS = [
    ("North", "Nora Singh (North Regional Lead)"),
    ("South", "Samir Rao (South Regional Lead)"),
    ("East", "Esha Das (East Regional Lead)"),
    ("West", "Wesley Chen (West Regional Lead)"),
    ("Central Security", "Chief Vance (Central Security Desk)"),
    ("Central Fallback", "Triage Officer (Fallback & Correction Queue)"),
]

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class ClosingConnection(sqlite3.Connection):
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
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          zone TEXT NOT NULL UNIQUE,
          available INTEGER NOT NULL DEFAULT 1,
          capacity INTEGER NOT NULL DEFAULT 8
        );
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY,
          reporter_name TEXT NOT NULL,
          reporter_contact TEXT NOT NULL,
          atm_id TEXT NOT NULL,
          error_code TEXT NOT NULL,
          description TEXT NOT NULL,
          category TEXT NOT NULL,
          priority TEXT NOT NULL,
          zone TEXT NOT NULL,
          status TEXT NOT NULL,
          handler_id INTEGER REFERENCES handlers(id),
          backup_handler_id INTEGER REFERENCES handlers(id),
          escalation TEXT,
          validation_outcome TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS reports_atm ON reports(atm_id);
        CREATE INDEX IF NOT EXISTS reports_status ON reports(status);
        CREATE INDEX IF NOT EXISTS reports_priority ON reports(priority);
        """)
        # Safe column addition if DB already existed
        cols = [r["name"] for r in db.execute("PRAGMA table_info(reports)").fetchall()]
        if "validation_outcome" not in cols:
            try:
                db.execute("ALTER TABLE reports ADD COLUMN validation_outcome TEXT")
            except sqlite3.OperationalError:
                pass

        for zone, name in DEFAULT_HANDLERS:
            db.execute("INSERT OR IGNORE INTO handlers(name,zone) VALUES (?,?)", (name, zone))


# ============================================================================
# VALIDATION & CLASSIFICATION LOGIC
# ============================================================================

def extract_atm_prefix(value: str) -> Optional[str]:
    """Extracts the 3-char prefix from an ATM ID (e.g. NOR from ATMNOR1001 or ATM-NOR-1001)."""
    clean = value.upper().replace("-", "")
    if clean.startswith("ATM") and len(clean) >= 6:
        return clean[3:6]
    return None

def validate_atm_id(value: str) -> Dict[str, Any]:
    """Validates ATM ID using both formal DFA and Regex."""
    clean = str(value or "").strip().upper()
    if not clean:
        return {
            "valid": False, "dfa": False, "regex": False, "agree": True,
            "prefix": None, "zone": None,
            "message": "ATM ID cannot be empty. Format: ATM[3-alpha][4-digit] (e.g. ATMNOR1001 or ATM-NOR-1001)."
        }

    dfa_res = ATM_DFA.simulate(clean)
    dfa_valid = dfa_res["accepted"]
    regex_valid = bool(ATM_REGEX.fullmatch(clean))
    
    prefix = extract_atm_prefix(clean)
    zone = PREFIX_TO_ZONE.get(prefix) if prefix else None
    
    # Supported prefix check
    supported = zone is not None
    valid = dfa_valid and regex_valid and supported

    if not (dfa_valid or regex_valid):
        msg = f"Invalid format: '{clean}'. Expected ATM[3-alpha][4-digit] (e.g. ATMNOR1001 or ATM-NOR-1001)."
    elif not supported:
        msg = f"Unknown regional prefix '{prefix}'. Supported prefixes: NOR, SOU, EAS, WES."
    else:
        msg = f"Valid ATM ID. Regional Zone: {zone}."

    return {
        "valid": valid,
        "dfa": dfa_valid,
        "regex": regex_valid,
        "agree": dfa_valid == regex_valid,
        "prefix": prefix,
        "zone": zone,
        "message": msg,
        "dfa_trace": dfa_res["trace"],
        "final_state": dfa_res["final_state"],
    }

def validate_error_code(value: str) -> Dict[str, Any]:
    """Validates Error Code using both formal DFA and Regex."""
    clean = str(value or "").strip().upper()
    if not clean:
        return {
            "valid": False, "dfa": False, "regex": False, "agree": True,
            "message": "Error code cannot be empty. Format: E[2-digit][1-alpha] (e.g. E01H)."
        }

    dfa_res = ERROR_CODE_DFA.simulate(clean)
    dfa_valid = dfa_res["accepted"]
    regex_valid = bool(ERROR_CODE_REGEX.fullmatch(clean))
    
    # Backwards-compatibility for legacy codes like HW-104
    legacy_valid = bool(LEGACY_ERROR_REGEX.fullmatch(clean))
    
    valid = (dfa_valid and regex_valid) or legacy_valid
    agree = (dfa_valid == regex_valid) if not legacy_valid else True

    if not valid:
        msg = f"Invalid error code '{clean}'. Expected E[2-digit][1-alpha] (e.g. E01H or E-01-H)."
    else:
        msg = f"Valid error code '{clean}'."

    return {
        "valid": valid,
        "dfa": dfa_valid or legacy_valid,
        "regex": regex_valid or legacy_valid,
        "agree": agree,
        "message": msg,
        "dfa_trace": dfa_res["trace"],
        "final_state": dfa_res["final_state"],
    }

def classify(description: str, error_code: str = "") -> Tuple[Optional[str], str]:
    """
    Classifies report into exactly 5 categories: Hardware, Network, Cash-Handling, Software, Security.
    Edge cases handled:
    - Multiple matches: deterministic priority rule: Security > Cash-Handling > Network > Software > Hardware.
    - Unknown/unmapped codes: returns (None, 'Unmapped') without silently defaulting!
    Returns (category, reason).
    """
    text = f"{description} {error_code}".lower()
    matched_categories: List[str] = []

    # 1. Check keyword matches
    for cat in CATEGORY_PRIORITY_ORDER:
        keywords = CATEGORY_KEYWORDS[cat]
        if any(kw in text for kw in keywords):
            matched_categories.append(cat)

    if matched_categories:
        # Multiple classification patterns: deterministic priority rule
        selected = matched_categories[0]
        if len(matched_categories) > 1:
            reason = f"Conflict detected ({', '.join(matched_categories)}). Resolved by deterministic priority rule to '{selected}'."
        else:
            reason = f"Classified by keyword detection to '{selected}'."
        return selected, reason

    # 2. Check structured error code mappings
    clean_code = error_code.strip().upper()
    # Match formal E[2-digit][1-alpha] format (e.g. E01H -> 'H')
    e_match = re.match(r"^E-?\d{2}-?([A-Z])$", clean_code)
    if e_match:
        suffix_char = e_match.group(1)
        if suffix_char in CODE_CATEGORY_MAP:
            cat = CODE_CATEGORY_MAP[suffix_char]
            return cat, f"Classified by error code type suffix '{suffix_char}' to '{cat}'."

    # Legacy code prefix check (e.g. HW-104 -> 'HW')
    code_prefix = clean_code.split("-")[0] if "-" in clean_code else ""
    if code_prefix and code_prefix in CODE_CATEGORY_MAP:
        cat = CODE_CATEGORY_MAP[code_prefix]
        return cat, f"Classified by error code prefix '{code_prefix}' to '{cat}'."

    # 3. Handle unknown or unmapped codes without silently assigning a valid category!
    return None, "Unmapped: code and description did not match any predefined category."

def priority_for(description: str, error_code: str = "", category: Optional[str] = None, user_urgency: str = "") -> str:
    """Calculates report priority, respecting user urgency and emergency security overrides."""
    text = f"{description} {error_code}".lower()
    
    # Emergency / Critical Security Override
    if category == "Security" or any(x in text for x in ("fraud", "skimming", "tamper", "security", "forced", "emergency", "intrusion")):
        return "Critical"
    
    # User-specified urgency override if higher
    urgency_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    user_prio = user_urgency.capitalize() if user_urgency.capitalize() in urgency_rank else "Low"

    # Pattern-based priority
    if any(x in text for x in ("cash-out", "all atm", "branch down", "dispenser jam", "offline", "urgent", "system crash")):
        calc_prio = "High"
    elif any(x in text for x in ("degraded", "intermittent", "slow", "receipt", "sensor")):
        calc_prio = "Medium"
    else:
        calc_prio = "Low"

    # Select whichever is more urgent (lower rank index)
    if urgency_rank.get(user_prio, 3) < urgency_rank.get(calc_prio, 3):
        return user_prio
    return calc_prio


# ============================================================================
# DISPATCH & ASSIGNMENT ALGORITHM (Part B)
# ============================================================================

def assign_handler(
    db: sqlite3.Connection,
    zone: Optional[str],
    category: Optional[str],
    priority: str,
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    BCS502 Dispatch Algorithm:
    1. Security errors bypass all regional teams and go directly to central security desk.
    2. Unknown zone or unmapped routing key: route to central fallback / correction queue.
    3. Regional routing: checks primary handler availability and capacity.
    4. If primary unavailable/full: select eligible backup handler from other zones or waiting queue.
    5. Priority override: record escalation decisions.
    """
    all_handlers = db.execute("""
        SELECT h.*, 
               (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') AS load
        FROM handlers h
        ORDER BY h.id
    """).fetchall()

    escalations: List[str] = []
    if priority == "Critical":
        escalations.append("Priority Override: Emergency protocol triggered.")

    # 1. SECURITY INCIDENT BYPASS
    if category == "Security":
        sec_handler = next((h for h in all_handlers if h["zone"] == "Central Security"), None)
        if sec_handler and sec_handler["available"] and sec_handler["load"] < sec_handler["capacity"]:
            escalations.append("Security Incident: Bypassed regional teams directly to Central Security Desk.")
            return sec_handler["id"], None, " ".join(escalations)
        elif sec_handler:
            escalations.append("Central Security Desk at capacity/unavailable; placed in High Priority Security Queue.")
            return None, None, " ".join(escalations)

    # 2. UNKNOWN ZONE / UNMAPPED ROUTING KEY -> CENTRAL FALLBACK QUEUE
    if not zone or zone not in ("North", "South", "East", "West"):
        fallback_handler = next((h for h in all_handlers if h["zone"] == "Central Fallback"), None)
        escalations.append("Unknown zone/prefix: Sent to Central Fallback & Correction Queue for triage.")
        fid = fallback_handler["id"] if fallback_handler and fallback_handler["available"] else None
        return fid, None, " ".join(escalations)

    # 3. REGIONAL ROUTING
    local_handlers = [h for h in all_handlers if h["zone"] == zone]
    eligible_local = [h for h in local_handlers if h["available"] and h["load"] < h["capacity"]]
    chosen = min(eligible_local, key=lambda h: h["load"]) if eligible_local else None

    # Other regional handlers for backup
    other_regional = [
        h for h in all_handlers
        if h["zone"] not in (zone, "Central Security", "Central Fallback")
        and h["available"] and h["load"] < h["capacity"]
    ]
    backup = min(other_regional, key=lambda h: h["load"]) if other_regional else None

    if chosen:
        return chosen["id"], backup["id"] if backup else None, " ".join(escalations) if escalations else None

    # Primary handler unavailable or capacity exceeded -> Failover to Backup
    if backup:
        escalations.append(f"Regional handler for {zone} unavailable/at capacity; failover assigned to {backup['zone']} backup.")
        return backup["id"], None, " ".join(escalations)

    # No handler available across the network -> Waiting queue
    escalations.append("All eligible regional handlers at capacity; report placed in Waiting Queue.")
    return None, None, " ".join(escalations)


def report_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["handler"] = data.pop("handler_name", None)
    data["backup_handler"] = data.pop("backup_name", None)
    if "validation_outcome" in data and data["validation_outcome"]:
        try:
            data["validation_outcome"] = json.loads(data["validation_outcome"])
        except Exception:
            pass
    return data

def report_query(db: sqlite3.Connection, where: str = "", params: tuple = ()) -> List[Dict[str, Any]]:
    rows = db.execute(f"""
        SELECT r.*, h.name AS handler_name, b.name AS backup_name
        FROM reports r
        LEFT JOIN handlers h ON r.handler_id=h.id
        LEFT JOIN handlers b ON r.backup_handler_id=b.id
        {where}
        ORDER BY 
          CASE r.priority 
            WHEN 'Critical' THEN 0 
            WHEN 'High' THEN 1 
            WHEN 'Medium' THEN 2 
            ELSE 3 
          END,
          r.created_at DESC
    """, params).fetchall()
    return [report_dict(row) for row in rows]


# ============================================================================
# FLASK APPLICATION & API ROUTES
# ============================================================================

app = Flask(__name__)
CORS(app)
init_db()

@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "ATM Error Logger & Dispatcher",
        "version": "2.0.0",
        "standards": ["BCS503: Automata Theory (DFA)", "BCS502: Computer Networks (Routing)"],
        "database": str(DB_PATH)
    })

@app.post("/api/validate")
def validate_endpoint():
    body = request.get_json(silent=True) or {}
    atm_raw = str(body.get("atm_id", "")).strip()
    code_raw = str(body.get("error_code", "")).strip()
    desc_raw = str(body.get("description", "")).strip()
    user_urgency = str(body.get("urgency", "")).strip()

    atm_val = validate_atm_id(atm_raw) if atm_raw else None
    code_val = validate_error_code(code_raw) if code_raw else None

    category, reason = classify(desc_raw, code_raw) if (desc_raw or code_raw) else (None, "")
    priority = priority_for(desc_raw, code_raw, category, user_urgency) if (desc_raw or code_raw) else None

    # Routing preview
    zone = atm_val.get("zone") if atm_val else None
    routing_target = "Central Security Desk" if category == "Security" else (f"{zone} Regional Support" if zone else "Central Fallback Queue")

    return jsonify({
        "atm": atm_val,
        "error_code": code_val,
        "error_code_valid": code_val["valid"] if code_val else False,
        "category": category,
        "classification_reason": reason,
        "priority": priority,
        "routing_preview": routing_target,
    })

@app.post("/api/dfa-simulate")
def dfa_simulate():
    """Allows testing strings against the formal DFA with step-by-step state trace."""
    body = request.get_json(silent=True) or {}
    dfa_type = body.get("type", "atm").lower()
    input_str = str(body.get("input", "")).strip().upper()

    if dfa_type == "atm":
        res = ATM_DFA.simulate(input_str)
        regex_match = bool(ATM_REGEX.fullmatch(input_str))
        formal_lang = "L = { 'ATM' + [A-Z]{3} + [0-9]{4} }"
    else:
        res = ERROR_CODE_DFA.simulate(input_str)
        regex_match = bool(ERROR_CODE_REGEX.fullmatch(input_str))
        formal_lang = "L = { 'E' + [0-9]{2} + [A-Z] }"

    return jsonify({
        "input": input_str,
        "type": dfa_type,
        "formal_language": formal_lang,
        "dfa_accepted": res["accepted"],
        "regex_accepted": regex_match,
        "agree": res["accepted"] == regex_match,
        "final_state": res["final_state"],
        "trace": res["trace"],
    })

@app.get("/api/reports")
def get_reports():
    with connect() as db:
        return jsonify(report_query(db))

@app.post("/api/reports")
def create_report():
    body = request.get_json(silent=True) or {}
    name = str(body.get("reporter_name", "")).strip()
    contact = str(body.get("reporter_contact", "")).strip()
    atm = str(body.get("atm_id", "")).strip().upper()
    code = str(body.get("error_code", "")).strip().upper()
    description = str(body.get("description", "")).strip()
    user_urgency = str(body.get("urgency", "")).strip()

    errors = {}
    if not name:
        errors["reporter_name"] = "Reporter name is required."
    if not contact:
        errors["reporter_contact"] = "Reporter contact information is required."

    atm_validation = validate_atm_id(atm)
    if not atm_validation["valid"]:
        errors["atm_id"] = atm_validation["message"]

    code_validation = validate_error_code(code)
    if not code_validation["valid"]:
        errors["error_code"] = code_validation["message"]

    if len(description) < 5:
        errors["description"] = "Please describe the incident in at least 5 characters."

    if errors:
        return jsonify({"error": "Validation failed.", "fields": errors}), 400

    # Classification & Edge Cases
    category, classification_reason = classify(description, code)
    if not category:
        category = "Hardware"  # Documented safe fallback if description is completely novel
        classification_reason = "Fallback: Unmapped patterns assigned to general Hardware queue."

    priority = priority_for(description, code, category, user_urgency)
    zone = atm_validation["zone"] or "Central Fallback"

    validation_outcome = json.dumps({
        "atm_dfa": atm_validation["dfa"],
        "atm_regex": atm_validation["regex"],
        "code_dfa": code_validation["dfa"],
        "code_regex": code_validation["regex"],
        "classification_reason": classification_reason,
        "validated_at": now(),
    })

    rid = f"ATM-{uuid.uuid4().hex[:10].upper()}"
    created = now()

    try:
        with connect() as db:
            handler, backup, escalation = assign_handler(db, zone, category, priority)
            status = "Assigned" if handler else "Pending"
            db.execute("""
                INSERT INTO reports (
                    id, reporter_name, reporter_contact, atm_id, error_code,
                    description, category, priority, zone, status,
                    handler_id, backup_handler_id, escalation, validation_outcome,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                rid, name, contact, atm, code,
                description, category, priority, zone, status,
                handler, backup, escalation, validation_outcome,
                created, created
            ))
            result = report_query(db, "WHERE r.id=?", (rid,))[0]
        return jsonify(result), 201
    except sqlite3.Error as exc:
        return jsonify({"error": f"Database persistence failure: {exc}"}), 500

@app.get("/api/reports/<report_id>")
def get_report(report_id: str):
    with connect() as db:
        found = report_query(db, "WHERE r.id=?", (report_id.upper(),))
    if not found:
        return jsonify({"error": "No report found with that ID."}), 404
    return jsonify(found[0])

@app.patch("/api/reports/<report_id>/status")
def update_status(report_id: str):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    allowed = ("Pending", "Assigned", "In Progress", "Resolved")
    if status not in allowed:
        return jsonify({"error": f"Status must be one of: {', '.join(allowed)}."}), 400

    with connect() as db:
        row = db.execute("SELECT * FROM reports WHERE id=?", (report_id.upper(),)).fetchone()
        if not row:
            return jsonify({"error": "No report found with that ID."}), 404
        db.execute("UPDATE reports SET status=?, updated_at=? WHERE id=?", (status, now(), report_id.upper()))
        return jsonify(report_query(db, "WHERE r.id=?", (report_id.upper(),))[0])

@app.get("/api/handlers")
def get_handlers():
    with connect() as db:
        rows = db.execute("""
            SELECT h.*, 
                   (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') AS load
            FROM handlers h 
            ORDER BY h.id
        """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.patch("/api/handlers/<int:handler_id>")
def update_handler(handler_id: int):
    body = request.get_json(silent=True) or {}
    with connect() as db:
        row = db.execute("SELECT * FROM handlers WHERE id=?", (handler_id,)).fetchone()
        if not row:
            return jsonify({"error": "Handler not found."}), 404

        available = body.get("available", row["available"])
        capacity = body.get("capacity", row["capacity"])
        try:
            capacity = int(capacity)
        except (ValueError, TypeError):
            return jsonify({"error": "Capacity must be a positive integer."}), 400
        if capacity < 1:
            return jsonify({"error": "Capacity must be a positive integer."}), 400

        db.execute("UPDATE handlers SET available=?, capacity=? WHERE id=?", (int(bool(available)), capacity, handler_id))
        updated = db.execute("""
            SELECT h.*, (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') AS load 
            FROM handlers h WHERE id=?
        """, (handler_id,)).fetchone()
        return jsonify(dict(updated))

@app.get("/api/routing")
def get_routing():
    with connect() as db:
        handlers = [dict(r) for r in db.execute("""
            SELECT h.*, (SELECT COUNT(*) FROM reports r WHERE r.handler_id=h.id AND r.status!='Resolved') AS load 
            FROM handlers h ORDER BY h.id
        """)]
        reports = report_query(db)

    # Detailed routing table
    mappings = [
        {"prefix": "NOR / 100", "zone": "North", "target": "North Regional Support", "handler": next((h["name"] for h in handlers if h["zone"] == "North"), "Nora Singh")},
        {"prefix": "SOU / 200", "zone": "South", "target": "South Regional Support", "handler": next((h["name"] for h in handlers if h["zone"] == "South"), "Samir Rao")},
        {"prefix": "EAS / 300", "zone": "East", "target": "East Regional Support", "handler": next((h["name"] for h in handlers if h["zone"] == "East"), "Esha Das")},
        {"prefix": "WES / 400", "zone": "West", "target": "West Regional Support", "handler": next((h["name"] for h in handlers if h["zone"] == "West"), "Wesley Chen")},
        {"prefix": "SEC (ANY)", "zone": "Security", "target": "Central Security Desk (BYPASS)", "handler": next((h["name"] for h in handlers if h["zone"] == "Central Security"), "Chief Vance")},
        {"prefix": "OTHER / UNMAPPED", "zone": "Central Fallback", "target": "Central Correction Queue", "handler": next((h["name"] for h in handlers if h["zone"] == "Central Fallback"), "Triage Officer")},
    ]

    queued = [r for r in reports if r["status"] == "Pending" and not r["handler"]]

    return jsonify({
        "mappings": mappings,
        "handlers": handlers,
        "reports": reports,
        "queued": queued,
        "security_bypass_rule": "Security incidents bypass regional routing and dispatch directly to the Central Security Desk.",
        "fallback_rule": "Unknown prefixes and unmapped routing keys dispatch to the Central Fallback Queue."
    })

@app.get("/api/analytics")
def get_analytics():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

        def grouped(field: str):
            return [dict(r) for r in db.execute(f"SELECT {field} AS name, COUNT(*) AS value FROM reports GROUP BY {field} ORDER BY {field}")]

        statuses = {r["name"]: r["value"] for r in grouped("status")}
        resolved = statuses.get("Resolved", 0)
        unresolved = total - resolved

        return jsonify({
            "total": total,
            "pending": statuses.get("Pending", 0),
            "assigned": statuses.get("Assigned", 0),
            "in_progress": statuses.get("In Progress", 0),
            "resolved": resolved,
            "unresolved": unresolved,
            "zones": grouped("zone"),
            "categories": grouped("category"),
            "priorities": grouped("priority"),
            "statuses": grouped("status"),
            "daily": [dict(r) for r in db.execute("""
                SELECT substr(created_at,1,10) AS name, COUNT(*) AS value 
                FROM reports GROUP BY name ORDER BY name DESC LIMIT 14
            """)]
        })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
