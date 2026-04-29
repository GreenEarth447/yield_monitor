# Yield Monitor

Web-based yield monitoring dashboard built with FastAPI + PostgreSQL. Includes a
live three-panel dashboard, a manual test entry form, and a Selenium end-to-end
test that validates the yield calculation.

## Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2.x
- **Database:** PostgreSQL
- **Frontend:** HTML / CSS / vanilla JS, Chart.js
- **Tests:** Selenium (Chrome)

## Project layout

```
.
├── main.py             FastAPI app + endpoints
├── database.py         SQLAlchemy engine, session, model
├── templates/
│   └── index.html      Single-page dashboard + manual test modal
├── test_yield.py       Selenium end-to-end yield test
├── requirements.txt
└── README.md
```

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Provision PostgreSQL

For a fresh local install, run the bundled setup script. It creates the
`sitewise_admin` role and `yield_monitor` database (idempotent):

```bash
./setup_db.sh
```

The default connection string is:

```
postgresql+psycopg2://sitewise_admin:sitewise_dev_2026@localhost:5432/yield_monitor
```

Override it for deployment by exporting `DATABASE_URL` (also accepts the
`postgres://` scheme used by Render/Railway/Heroku — it's auto-rewritten):

```bash
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/dbname"
```

The schema is created automatically on app startup.

### 3. Run the app

```bash
python3 main.py
```

Open http://localhost:8000.

Override host/port/reload via env vars: `HOST=127.0.0.1 PORT=9000 RELOAD=0 python3 main.py`.

## API

| Method | Path     | Description                                     |
| ------ | -------- | ----------------------------------------------- |
| POST   | `/tests` | Insert a new test record                        |
| GET    | `/tests` | List all test records (newest first)            |
| GET    | `/stats` | Per-part-number yield statistics                |
| GET    | `/daily` | Unit count per day for the last 7 days          |

`POST /tests` body:

```json
{ "serial_number": "SN-001", "part_number": "001PN001", "status": true }
```

`status` is `true` for Pass, `false` for Fail. Allowed `part_number` values:
`001PN001`, `002PN002`, `003PN003`.

## Selenium test

The script inserts 5 records for `001PN001` (3 pass, 2 fail) and asserts the
yield gauge reads **60%**.

```bash
# App must be running first
BASE_URL=http://localhost:8000 python test_yield.py
```

Set `HEADLESS=0` to watch the browser. Requires Chrome / Chromedriver on PATH
(Selenium 4.x auto-downloads a matching driver via Selenium Manager).

## Deployment

Set `DATABASE_URL` to your managed Postgres instance and start the app with:

```bash
PORT=$PORT python3 main.py
```

(Or `uvicorn main:app --host 0.0.0.0 --port $PORT` if your platform expects that form.)

Works on Replit, Render, Railway, and PythonAnywhere with no code changes.
