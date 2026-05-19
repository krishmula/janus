"""FastAPI application: interact and extract endpoints for the Janus agent API."""

from __future__ import annotations

import logging
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import executor
from app.model import ExtractRequest, InteractRequest

load_dotenv()

logger = logging.getLogger(__name__)


async def fetch_extraction(run_id: str, schema_name: str) -> dict:
    """Return structured extraction for a completed run.

    Placeholder until trace storage and extraction are implemented.
    """
    return {"run_id": run_id, "schema_name": schema_name, "items": []}


def create_app() -> FastAPI:
    application = FastAPI(
        title="Janus",
        description="Browser agent control plane API",
    )

    @application.middleware("http")
    async def structured_logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
        response.headers["X-Request-Id"] = request_id
        return response

    @application.post("/api/interact")
    async def interact(body: InteractRequest) -> JSONResponse:
        goal = body.prompt
        run_id, steps, final_result = await executor.run(goal)

        logger.debug("Interact completed with %d step(s)", len(steps))

        return JSONResponse(
            {
                "run_id": run_id,
                "goal": goal,
                "steps": steps,
                "total_steps": len(steps),
                "final_result": final_result,
                "final_screenshot": final_result.get("screenshot_path") if final_result else None,
            }
        )

    @application.post("/api/extract")
    async def extract(body: ExtractRequest) -> JSONResponse:
        result = await fetch_extraction(body.run_id, body.schema_name)
        return JSONResponse(result)

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Hello, World!"}

    @application.get("/health")
    async def health_check() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
