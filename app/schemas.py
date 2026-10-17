from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import validate_url_syntax


class RequestConfigBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    method: Literal["GET", "POST", "PUT", "DELETE"]
    url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | list[Any] | None = None
    monitor_enabled: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_url_syntax(value)


class RequestConfigCreate(RequestConfigBase):
    pass


class RequestConfigUpdate(RequestConfigBase):
    pass


class RequestConfigRead(RequestConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class RunResult(BaseModel):
    history_id: int
    request_config_id: int | None
    name: str
    method: str
    url: str
    status_code: int | None
    latency_ms: float | None
    response_headers: dict[str, str]
    response_body: str | None
    response_json: Any | None = None
    error: str | None = None
    created_at: datetime


class HistoryRead(RunResult):
    request_headers: dict[str, str]
    query_params: dict[str, str]
    request_body: dict[str, Any] | list[Any] | None


class HealthItem(BaseModel):
    request_config_id: int
    name: str
    url: str
    status: Literal["healthy", "unhealthy", "error", "not_run"]
    status_code: int | None
    latency_ms: float | None
    last_checked: datetime | None
    error: str | None = None
