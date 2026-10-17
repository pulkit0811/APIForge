import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.security import UnsafeUrlError, validate_public_destination

MAX_RESPONSE_BYTES = 1_048_576
REQUEST_TIMEOUT_SECONDS = 10.0


class RequestExecutionError(Exception):
    pass


@dataclass
class ExecutionResult:
    status_code: int | None
    latency_ms: float | None
    response_headers: dict[str, str]
    response_body: str | None
    error: str | None


def execute_request(method: str, url: str, headers: dict[str, str], query_params: dict[str, str], body: Any) -> ExecutionResult:
    try:
        safe_url = validate_public_destination(url)
        started = time.perf_counter()
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
            with client.stream(method, safe_url, headers=headers, params=query_params, json=body) as response:
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise RequestExecutionError("Response exceeded the 1 MB size limit")
                    chunks.append(chunk)
                raw_body = b"".join(chunks)
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                return ExecutionResult(
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    response_headers=dict(response.headers),
                    response_body=raw_body.decode(response.encoding or "utf-8", errors="replace"),
                    error=None,
                )
    except UnsafeUrlError as exc:
        return ExecutionResult(None, None, {}, None, str(exc))
    except RequestExecutionError as exc:
        return ExecutionResult(None, None, {}, None, str(exc))
    except httpx.TimeoutException:
        return ExecutionResult(None, None, {}, None, "Request timed out")
    except httpx.HTTPError as exc:
        return ExecutionResult(None, None, {}, None, f"HTTP client error: {exc}")
    except (OSError, UnicodeError) as exc:
        return ExecutionResult(None, None, {}, None, f"Request failed: {exc}")


def parse_json_body(value: str | None) -> Any | None:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None
