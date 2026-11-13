# ATM Error Logger & Dispatcher

A web application for reporting ATM incidents, routing them to support teams, and tracking resolution across four regions.

## Features

- **Report submission** - validates ATM IDs and error codes, then detects incident category and priority.
- **Report tracking** - search by report ID and follow status, handler, and submission details.
- **Handler console** - manage handler availability, capacity, and report status.
- **Routing dashboard** - view regional mappings, assignments, escalations, and queued reports.
- **Analytics** - explore report trends by zone, category, status, and priority.
- **SQLite storage** - reports, handler settings, and analytics use live database records.

## Tech stack

- Frontend: React, Vite, React Router, Axios, Recharts
- Backend: Python, Flask, SQLite
- Tests: Python `unittest`

## Run locally

You'll need Python 3.10+ and Node.js 20+.

### 1. Start the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The API runs at `http://127.0.0.1:5000`. SQLite is created at `backend/atm_errors.db` on first launch.

### 2. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, usually `http://127.0.0.1:5173`.

To use a different API address, set `VITE_API_URL` before starting Vite. The default is `http://127.0.0.1:5000/api`.

### Production build

```powershell
cd frontend
npm run build
```

## Routing and validation rules

- ATM IDs use the format `ATM-<zone>-<terminal>`, for example `ATM-100-1234`.
- Zone prefixes: `100` North, `200` South, `300` East, `400` West.
- Error codes use 2-4 letters followed by a hyphen and 3-5 digits, for example `HW-104`.
- Reports are assigned to an available handler with capacity. If the regional team is full, dispatch can use a backup handler; if no handler is available, the report stays queued.
- Critical security reports trigger an escalation.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check API and database status |
| `POST` | `/api/validate` | Preview validation, category, and priority |
| `POST` | `/api/reports` | Validate, route, and save a report |
| `GET` | `/api/reports` | List reports |
| `GET` | `/api/reports/<id>` | Find a report by ID |
| `PATCH` | `/api/reports/<id>/status` | Update a report status |
| `GET` | `/api/handlers` | View handler workload and availability |
| `PATCH` | `/api/handlers/<id>` | Update handler capacity or availability |
| `GET` | `/api/routing` | View routing mappings and dispatch data |
| `GET` | `/api/analytics` | View database-backed report summaries |

## Run the tests

From the `backend` directory:

```powershell
python -m unittest discover -s tests -v
```

The suite contains 25 cases covering validation, classification, dispatch, persistence, analytics, and the report workflow.

## Project layout

```text
backend/
  app.py                 Flask API and application logic
  requirements.txt       Python dependencies
  tests/test_app.py       Backend test suite
frontend/
  src/App.jsx             Dashboard pages and application views
  src/main.jsx            React entry point
  src/styles.css          Responsive styles
  package.json            Frontend scripts and dependencies
```





