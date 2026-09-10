# WhatsNews Backend

FastAPI backend for WhatsNews. **This file is a quick-start only — it is
not kept in sync with the API surface.** For the current architecture,
full endpoint list, pipeline design, environment variables, and technical
debt, see [`docs/ENGINEERING.md`](../docs/ENGINEERING.md); it is the single
source of truth for this project and is updated continuously, unlike this
file.

## Endpoints

40+ endpoints across public/auth-gated/admin routes — see
[`docs/ENGINEERING.md`](../docs/ENGINEERING.md)'s
API section for the full list, or run the server and open
http://127.0.0.1:8000/docs for live, always-accurate interactive docs.

## Setup

### 1. Create a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

The API will be available at: http://127.0.0.1:8000

## Interactive Docs

FastAPI generates interactive docs automatically:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc:       http://127.0.0.1:8000/redoc

## Operator docs

- [Google Sheets export](docs/google-sheets-export.md) — setup, curl, troubleshooting
