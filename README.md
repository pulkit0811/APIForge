# APIForge

APIForge is a compact REST API testing and monitoring dashboard built with FastAPI, SQLAlchemy, SQLite, Pydantic, and a responsive vanilla JavaScript frontend.

## Features

- Create, edit, delete, and run saved GET, POST, PUT, and DELETE requests
- Configure JSON headers, query parameters, and request bodies
- View status, latency, response headers, and formatted JSON response content
- Persist request history and rerun any previous request
- Monitor saved endpoints and review response-time history on a lightweight chart
- Interactive API documentation at `/docs`
- Built-in sample JSON endpoints at `/api/sample/hello`, `/api/sample/echo`, and `/api/sample/status/{code}`
- SSRF protections for request execution: only HTTP(S), no credentials, no localhost/private/link-local/reserved destinations, no automatic redirects
- 10-second request timeout and 1 MB response limit

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The database is created automatically on startup and seeded with two JSONPlaceholder examples.

## Test

```powershell
pytest
```

The application deliberately blocks localhost and private-network destinations in the request execution path. The built-in sample endpoints are available for demonstrating FastAPI itself and through `/docs`; they are not valid targets for the outbound request runner.

## API route groups

- `/api/requests` for saved request CRUD and `/api/requests/{id}/run`
- `/api/history` and `/api/history/{id}/rerun` for request history
- `/api/health` and `/api/health/check` for monitoring
- `/api/metrics/latency` for chart data
- `/api/sample/*` for demonstration endpoints
