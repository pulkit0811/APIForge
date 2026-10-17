import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db, init_db
from app.models import RequestConfig, RequestHistory
from app.runner import execute_request, parse_json_body
from app.schemas import HealthItem, HistoryRead, RequestConfigCreate, RequestConfigRead, RequestConfigUpdate, RunResult

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="APIForge", version="1.0.0", description="REST API testing and monitoring dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_samples()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "templates" / "index.html")


def seed_samples() -> None:
    with SessionLocal() as db:
        if db.scalar(select(RequestConfig.id).limit(1)) is not None:
            return
        db.add_all(
            [
                RequestConfig(name="JSONPlaceholder todo", method="GET", url="https://jsonplaceholder.typicode.com/todos/1", headers={}, query_params={}, body=None, monitor_enabled=True),
                RequestConfig(name="JSONPlaceholder create", method="POST", url="https://jsonplaceholder.typicode.com/posts", headers={"Content-Type": "application/json"}, query_params={}, body={"title": "APIForge", "body": "Portfolio demo", "userId": 1}, monitor_enabled=False),
            ]
        )
        db.commit()


def to_run_result(history: RequestHistory) -> RunResult:
    return RunResult(
        history_id=history.id,
        request_config_id=history.request_config_id,
        name=history.name,
        method=history.method,
        url=history.url,
        status_code=history.status_code,
        latency_ms=history.latency_ms,
        response_headers=history.response_headers,
        response_body=history.response_body,
        response_json=parse_json_body(history.response_body),
        error=history.error,
        created_at=history.created_at,
    )


def run_config(db: Session, config: RequestConfig) -> RequestHistory:
    result = execute_request(config.method, config.url, config.headers, config.query_params, config.body)
    history = RequestHistory(
        request_config_id=config.id,
        name=config.name,
        method=config.method,
        url=config.url,
        request_headers=config.headers,
        query_params=config.query_params,
        request_body=config.body,
        status_code=result.status_code,
        latency_ms=result.latency_ms,
        response_headers=result.response_headers,
        response_body=result.response_body,
        error=result.error,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


@app.get("/api/requests", response_model=list[RequestConfigRead])
def list_requests(db: Session = Depends(get_db)) -> list[RequestConfig]:
    return list(db.scalars(select(RequestConfig).order_by(desc(RequestConfig.updated_at))))


@app.post("/api/requests", response_model=RequestConfigRead, status_code=201)
def create_request(payload: RequestConfigCreate, db: Session = Depends(get_db)) -> RequestConfig:
    config = RequestConfig(**payload.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@app.get("/api/requests/{request_id}", response_model=RequestConfigRead)
def get_request(request_id: int, db: Session = Depends(get_db)) -> RequestConfig:
    config = db.get(RequestConfig, request_id)
    if not config:
        raise HTTPException(404, "Request configuration not found")
    return config


@app.put("/api/requests/{request_id}", response_model=RequestConfigRead)
def update_request(request_id: int, payload: RequestConfigUpdate, db: Session = Depends(get_db)) -> RequestConfig:
    config = db.get(RequestConfig, request_id)
    if not config:
        raise HTTPException(404, "Request configuration not found")
    for key, value in payload.model_dump().items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


@app.delete("/api/requests/{request_id}", status_code=204)
def delete_request(request_id: int, db: Session = Depends(get_db)) -> None:
    config = db.get(RequestConfig, request_id)
    if not config:
        raise HTTPException(404, "Request configuration not found")
    db.delete(config)
    db.commit()


@app.post("/api/requests/{request_id}/run", response_model=RunResult)
def execute_saved_request(request_id: int, db: Session = Depends(get_db)) -> RunResult:
    config = db.get(RequestConfig, request_id)
    if not config:
        raise HTTPException(404, "Request configuration not found")
    return to_run_result(run_config(db, config))


@app.get("/api/history", response_model=list[HistoryRead])
def list_history(limit: int = 50, db: Session = Depends(get_db)) -> list[RequestHistory]:
    limit = max(1, min(limit, 200))
    return list(db.scalars(select(RequestHistory).order_by(desc(RequestHistory.created_at)).limit(limit)))


@app.post("/api/history/{history_id}/rerun", response_model=RunResult)
def rerun_history(history_id: int, db: Session = Depends(get_db)) -> RunResult:
    history = db.get(RequestHistory, history_id)
    if not history:
        raise HTTPException(404, "History item not found")
    config = RequestConfig(name=history.name, method=history.method, url=history.url, headers=history.request_headers, query_params=history.query_params, body=history.request_body, monitor_enabled=False)
    result = execute_request(config.method, config.url, config.headers, config.query_params, config.body)
    rerun = RequestHistory(request_config_id=history.request_config_id, name=config.name, method=config.method, url=config.url, request_headers=config.headers, query_params=config.query_params, request_body=config.body, status_code=result.status_code, latency_ms=result.latency_ms, response_headers=result.response_headers, response_body=result.response_body, error=result.error)
    db.add(rerun)
    db.commit()
    db.refresh(rerun)
    return to_run_result(rerun)


@app.get("/api/health", response_model=list[HealthItem])
def health_dashboard(db: Session = Depends(get_db)) -> list[HealthItem]:
    configs = list(db.scalars(select(RequestConfig).where(RequestConfig.monitor_enabled.is_(True)).order_by(RequestConfig.name)))
    items: list[HealthItem] = []
    for config in configs:
        latest = db.scalar(select(RequestHistory).where(RequestHistory.request_config_id == config.id).order_by(desc(RequestHistory.created_at)).limit(1))
        if not latest:
            items.append(HealthItem(request_config_id=config.id, name=config.name, url=config.url, status="not_run", status_code=None, latency_ms=None, last_checked=None))
        else:
            items.append(HealthItem(request_config_id=config.id, name=config.name, url=config.url, status="healthy" if latest.status_code and latest.status_code < 400 else "unhealthy" if latest.status_code else "error", status_code=latest.status_code, latency_ms=latest.latency_ms, last_checked=latest.created_at, error=latest.error))
    return items


@app.post("/api/health/check", response_model=list[HealthItem])
def run_health_checks(db: Session = Depends(get_db)) -> list[HealthItem]:
    configs = list(db.scalars(select(RequestConfig).where(RequestConfig.monitor_enabled.is_(True))))
    for config in configs:
        run_config(db, config)
    return health_dashboard(db)


@app.get("/api/metrics/latency")
def latency_metrics(limit: int = 30, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 100))
    history = list(db.scalars(select(RequestHistory).where(RequestHistory.latency_ms.is_not(None)).order_by(desc(RequestHistory.created_at)).limit(limit)))
    return [{"timestamp": item.created_at.isoformat(), "name": item.name, "latency_ms": item.latency_ms, "status_code": item.status_code} for item in reversed(history)]


@app.get("/api/sample/hello")
def sample_hello() -> dict:
    return {"message": "Hello from APIForge", "service": "sample"}


@app.post("/api/sample/echo")
async def sample_echo(request: Request) -> dict:
    return {"received": await request.json()}


@app.get("/api/sample/status/{code}")
def sample_status(code: int) -> dict:
    if code < 100 or code > 599:
        raise HTTPException(400, "Status code must be between 100 and 599")
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=code, content={"status_code": code, "message": "Sample response"})
