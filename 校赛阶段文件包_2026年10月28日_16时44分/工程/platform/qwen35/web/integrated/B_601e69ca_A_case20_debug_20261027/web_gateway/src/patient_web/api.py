"""HTTP commands and SSE notifications; static console is only an integration aid."""

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Annotated
from typing import Literal

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .engine import TextEngine
from .delivery import TurnResult
from .evaluation import EvaluationResult
from .errors import GatewayError
from .manager import Coordinator

Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: Identifier


class CreateSession(Command):
    cache_mode: Literal["auto", "hit", "miss"] = "auto"


class SubmitTurn(Command):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def valid_text(cls, value):
        if not value.strip() or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Empty/control text")
        return value


class CancelTurn(Command):
    target_request_id: Identifier


class SelectBackend(Command):
    backend: Identifier


class DemoScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scenario: Literal["normal", "delayed", "wrong_fact", "timeout", "failure"]
    delay_s: float = Field(default=3.0, ge=0.2, le=10)


def sse_frame(event):
    event_id = f'{event["instance_id"]}:{event["seq"]}'
    return f'id: {event_id}\nevent: {event["event"]}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n'


def create_app(*, backend="native", project_root=None, output=None, threads=3,
               engine_factory=None, journal_capacity=256, demo_lab=False,
               generation_timeout_s=180, backend_options=None):
    if backend == "managed-pl" and engine_factory is None:
        raise ValueError("managed-pl requires an existing PS-owned NativePL instance")
    if demo_lab and (backend != "demo" or engine_factory is not None):
        raise ValueError("demo_lab requires the explicit built-in demo backend")
    if demo_lab:
        from .demo_lab import LabEngine
        engine_factory = LabEngine
    coordinator = Coordinator(engine_factory or
                              (lambda: TextEngine(backend, project_root, output, threads,
                                                  generation_timeout_s=generation_timeout_s)),
                              backend, journal_capacity, backend_options)

    @asynccontextmanager
    async def lifespan(app):
        coordinator.start()
        try:
            yield
        finally:
            await asyncio.to_thread(coordinator.close)

    app = FastAPI(title="KV260 文字问诊接口", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.coordinator = coordinator

    @app.exception_handler(GatewayError)
    async def gateway_error(request, error):
        return JSONResponse(status_code=error.status, content={"error": {
            "code": error.code, "message": error.message, "retryable": error.retryable}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Do not reflect arbitrary body content or potentially private questions in errors.
        return JSONResponse(status_code=400, content={"error": {
            "code": "INVALID_REQUEST", "message": "请求字段、长度或内容不符合接口约定。", "retryable": False}})

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and origin and origin != expected:
            return JSONResponse(status_code=403, content={"error": {
                "code": "ORIGIN_REJECTED", "message": "请从本机接口页面发起操作。", "retryable": False}})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/console.js", include_in_schema=False)
    def console_script():
        return FileResponse(Path(__file__).parent / "static" / "console.js", media_type="text/javascript")

    # Only packaged, named display assets are exposed; no filesystem path is accepted from the browser.
    @app.get("/display/{name}", include_in_schema=False)
    def display_asset(name: str):
        names = {"evaluation.css", "tokens.css", "clinic-background.png",
                 "chief-physician.png", "chief-physician-speaking.png"}
        if name not in names:
            raise GatewayError("ASSET_NOT_FOUND", "显示素材不存在。", 404)
        return FileResponse(Path(__file__).parent / "static" / name)

    @app.get("/ui/v1/status")
    def status():
        return dict(coordinator.status(), demo_lab=bool(demo_lab))

    @app.post("/ui/v1/backend", status_code=202)
    def select_backend(command: SelectBackend):
        return coordinator.select_backend(command.request_id, command.backend)

    if demo_lab:
        @app.get("/lab", include_in_schema=False)
        def lab_page():
            return FileResponse(Path(__file__).parent / "static" / "lab.html")

        @app.get("/lab.js", include_in_schema=False)
        def lab_script():
            return FileResponse(Path(__file__).parent / "static" / "lab.js", media_type="text/javascript")

        @app.get("/ui/v1/demo-lab")
        def lab_status():
            with coordinator.lock:
                coordinator._require_ready()
                return coordinator.engine.model.snapshot()

        @app.post("/ui/v1/demo-lab")
        def configure_lab(command: DemoScenario):
            with coordinator.lock:
                coordinator._require_ready()
                coordinator._idle()
                return coordinator.engine.model.arm(command.scenario, command.delay_s)

    @app.get("/ui/v1/cases")
    def cases():
        return {"selection": "random", "case_count": len(coordinator.cases())}

    @app.post("/ui/v1/sessions", status_code=201)
    def create_session(command: CreateSession):
        return coordinator.create_session(command.request_id, cache_mode=command.cache_mode)

    @app.get("/ui/v1/sessions/{session_id}")
    def snapshot(session_id: str):
        return coordinator.snapshot(session_id)

    @app.post("/ui/v1/sessions/{session_id}/turns", status_code=202)
    def turn(session_id: str, command: SubmitTurn):
        return coordinator.submit(session_id, command.request_id, command.text)

    @app.get("/ui/v1/sessions/{session_id}/turns/{request_id}", response_model=TurnResult)
    def turn_result(session_id: str, request_id: str):
        return coordinator.turn_result(session_id, request_id)

    @app.post("/ui/v1/sessions/{session_id}/cancel", status_code=202)
    def cancel(session_id: str, command: CancelTurn):
        return coordinator.cancel(session_id, command.request_id, command.target_request_id)

    @app.post("/ui/v1/sessions/{session_id}/finish")
    def finish(session_id: str, command: Command):
        return coordinator.finish(session_id, command.request_id)

    @app.get("/ui/v1/sessions/{session_id}/evaluation", response_model=EvaluationResult)
    def evaluation(session_id: str):
        return coordinator.evaluation(session_id)

    @app.get("/ui/v1/events")
    async def events(request: Request, session_id: str, after: int | None = Query(None, ge=0),
                     last_event_id: str | None = Header(None)):
        snapshot = coordinator.snapshot(session_id)
        cursor = after
        reset = False
        if cursor is None and last_event_id:
            try:
                instance, sequence = last_event_id.split(":", 1)
                cursor = int(sequence)
                if cursor < 0:
                    raise ValueError()
                reset = instance != coordinator.journal.instance_id
            except ValueError:
                raise GatewayError("INVALID_CURSOR", "事件恢复位置不合法。", 400)
        if cursor is not None and cursor > snapshot["cursor"] and not reset:
            raise GatewayError("INVALID_CURSOR", "事件恢复位置超过当前进度。", 400)

        async def stream():
            nonlocal cursor
            if cursor is None or reset:
                current = coordinator.snapshot(session_id)
                cursor = current["cursor"]
                yield sse_frame({"schema_version": "ui.v1", "instance_id": current["instance_id"],
                                 "seq": cursor, "event": "session.snapshot", "session_id": session_id,
                                 "request_id": None, "epoch": current["epoch"], "data": current})
            idle_ticks = 0
            while not await request.is_disconnected():
                batch, gap, latest = coordinator.event_batch(session_id, cursor)
                if gap:
                    current = coordinator.snapshot(session_id)
                    cursor = current["cursor"]
                    yield sse_frame({"schema_version": "ui.v1", "instance_id": current["instance_id"],
                                     "seq": cursor, "event": "session.snapshot", "session_id": session_id,
                                     "request_id": None, "epoch": current["epoch"],
                                     "data": dict(current, resync_reason="EVENT_BUFFER_EXPIRED")})
                else:
                    for item in batch:
                        yield sse_frame(item)
                    cursor = latest
                idle_ticks += 1
                if idle_ticks >= 200:
                    yield ": keepalive\n\n"
                    idle_ticks = 0
                await asyncio.sleep(0.05)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return app

