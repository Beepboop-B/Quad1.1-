# ATM Error Logger & Dispatcher (Sentinel)
**Scenario-Based Project: P7**  
*Integrating Automata Theory & Computability (BCS503) with Computer Networks (BCS502)*

---

## 📌 Project Overview

Sentinel is a responsive, web-based ATM Error Logger and Dispatcher application engineered to log, validate, classify, route, and track incidents across multi-regional ATM networks.

The application integrates:
- **BCS503 (Automata Theory and Computability)**: Formal Deterministic Finite Automata (DFA) state machines and equivalent regular expressions for identifier validation (`ATM[3-alpha][4-digit]`, `E[2-digit][1-alpha]`), 5-category incident classification, deterministic conflict resolution, and step-by-step state transition traces.
- **BCS502 (Computer Networks)**: Explicit regional routing table, dynamic dispatch algorithm, handler capacity management, backup failovers, priority overrides, and a dedicated **Central Security Desk Bypass**.

---

## 🚀 Key Modules & Architecture

### Part A & B: Automata & Network Routing Backend
1. **Formal DFA Simulators**:
   - `ATM_ID_DFA`: $M_{ATM} = (Q, \Sigma, \delta, q_0, \{q_{12}\})$ validating format `ATM[3-alpha][4-digit]` (e.g. `ATMNOR1001` or `ATM-NOR-1001`).
   - `ERROR_CODE_DFA`: $M_{Error} = (S, \Sigma, \delta_E, s_0, \{s_6\})$ validating format `E[2-digit][1-alpha]` (e.g. `E01H`, `E05X`).
   - Regex verification checking exact language equivalence and reporting step-by-step state traces.
2. **Five Predefined Classifications**:
   - `Hardware`
   - `Network`
   - `Cash-Handling`
   - `Software`
   - `Security`
3. **Deterministic Conflict Priority Rule**:
   - If conflicting patterns appear in the incident description or codes:  
     `Security > Cash-Handling > Network > Software > Hardware`
4. **Computer Networks Routing Table & Dispatch**:
   - **4 Regional Support Zones**:
     - `NOR` (or `100`): North Region -> Nora Singh (North Regional Lead)
     - `SOU` (or `200`): South Region -> Samir Rao (South Regional Lead)
     - `EAS` (or `300`): East Region -> Esha Das (East Regional Lead)
     - `WES` (or `400`): West Region -> Wesley Chen (West Regional Lead)
   - **Central Security Desk Bypass**: Security incidents bypass all regional teams and dispatch directly to the Central Security Desk with emergency escalation.
   - **Central Fallback & Correction Queue**: Unmapped or unknown prefixes route directly to triage.
   - **Handler Capacity & Availability**: Dynamic failover to eligible backup regional handlers if the primary handler is full or unavailable; waiting queue if network capacity is exceeded.
   - **Statuses**: `Pending`, `Assigned`, `In Progress`, `Resolved`.

---

### Part C: Responsive Frontend (React + Vite)
1. **Report Submission Interface (`/submit`)**:
   - Reporter details (name, contact).
   - Structured identifiers (`ATM ID`, `Error Code`) with live DFA and Regex validity badges.
   - Urgency dropdown (`Low`, `Medium`, `High`, `Critical`).
   - Incident description with real-time classification, priority detection, and routing destination preview.
   - Generates unique Report ID (`ATM-xxxxxxxxxx`).
2. **User Dashboard / Report Tracking (`/my-reports`)**:
   - Status counters (Total, Pending, Assigned, In Progress, Resolved).
   - Search by Report ID displaying assigned handler, backup, priority, status, and escalation notes.
3. **Handler Console (`/handlers`)**:
   - Manage workloads and availability toggles for Regional Handlers and Central Security Desk.
   - Advance report lifecycle status (`Pending` -> `Assigned` -> `In Progress` -> `Resolved`).
4. **Routing Management Dashboard (`/routing`)**:
   - Explicit prefix routing table and Central Security bypass rule display.
   - Handler load meters vs capacity.
   - Live dispatch decisions and queue monitors.
5. **Analytics Dashboard (`/analytics`)**:
   - Zone distribution chart (North, South, East, West, Central).
   - 5-category distribution pie chart.
   - Pipeline status bar chart.
   - Priority breakdown.
6. **Interactive DFA Simulator (`/dfa-simulator`)**:
   - Test bench to execute inputs against the DFA and Regex side-by-side.
   - Live step-by-step state transition table ($\text{Step}, \text{Char}, \text{From State} \to \text{To State}$).

---

### Part D: Testing & Verification
The test suite in [test_app.py](file:///c:/Users/chand/Downloads/Quad1.1-/backend/tests/test_app.py) contains **22 automated test cases** covering all 15 required assignment scenarios:
- Valid and invalid input formats with DFA and regex agreement.
- All five report categories and conflicting pattern resolution.
- Unknown routing zones, invalid codes, and fallback routing.
- Handler availability, capacity overflow, and backup dispatch.
- Emergency priority overrides and queue ordering.
- Status updates, persistence, search by ID, and DFA simulation traces.

---

## 🛠 Local Setup & Running

### Requirements
- Python 3.10+
- Node.js 20+

### 1. Run the Flask Backend
```powershell
cd backend
.venv\Scripts\Activate.ps1
python app.py
```
*API runs at `http://127.0.0.1:5000` with SQLite database `backend/atm_errors.db`.*

### 2. Run the React Frontend
In a separate terminal:
```powershell
cd frontend
npm run dev
```
*Open `http://127.0.0.1:5173` in your browser.*

### 3. Run Backend Unit Tests
```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
