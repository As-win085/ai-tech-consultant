from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.schemas import (
    AskRequest, AskResponse, ErrorResponse, ReadyReport,
    EscalationCreateRequest, EscalationResolveRequest,
)
from app.service import KnowledgeService, ServiceUnavailable, build_default_service

app = FastAPI(
    title="AI Tech Consultant - Knowledge Brain",
    description=(
        "Shared knowledge service for AI-powered business automation. Answers "
        "questions from the Brilliant Directories support knowledge base with "
        "verifiable citations, or abstains safely when evidence is insufficient."
    ),
    version="0.2.0",
)

import os
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_extra = [o.strip() for o in _raw_origins.split(",") if o.strip()]
_cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"] + _extra

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_service: KnowledgeService | None = None


def get_service() -> KnowledgeService:
    """Return the process-wide service, built lazily from the environment."""
    global _service
    if _service is None:
        _service = build_default_service()
    return _service


@app.get("/")
async def root():
    return {
        "message": "AI Tech Consultant Knowledge Brain",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "knowledge-brain",
        "version": "0.2.0",
    }


@app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
async def knowledge_chat():
    from app.chat_ui import CHAT_HTML
    return HTMLResponse(CHAT_HTML)


@app.post("/ingestion/run")
def start_ingestion():
    from app.ingestion import run_ingestion
    try:
        return run_ingestion()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "ingestion_unavailable", "message": "ingestion did not complete", "detail": type(exc).__name__}},
        )


@app.get("/ingestion/status")
def ingestion_status():
    from app.ingestion import get_ingestion_status
    try:
        return {"latest_run": get_ingestion_status()}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "ingestion_status_unavailable", "message": "ingestion status is unavailable", "detail": type(exc).__name__}},
        )


@app.post(
    "/ask",
    response_model=AskResponse,
    responses={503: {"model": ErrorResponse}},
    summary="Ask a grounded question",
    description=(
        "Retrieves relevant support-article chunks and returns a grounded answer "
        "with citations, or a safe abstention when evidence is insufficient. A "
        "valid but unanswerable question returns HTTP 200 with an abstention; "
        "only dependency failures return 503."
    ),
)
def ask(
    request: AskRequest,
    service: KnowledgeService = Depends(get_service),
) -> AskResponse:
    return service.ask(request)


@app.post("/query", response_model=AskResponse, include_in_schema=False)
def query_alias(
    request: AskRequest,
    service: KnowledgeService = Depends(get_service),
) -> AskResponse:
    """Compatibility alias for clients that still use the requirements route."""
    return service.ask(request)


@app.get(
    "/ready",
    response_model=ReadyReport,
    responses={503: {"model": ReadyReport}},
    summary="Dependency readiness",
    description=(
        "Reports readiness of the database, embedding provider, and chat provider. "
        "Distinguishes process health (/health) from dependency availability. "
        "Returns 503 when not fully ready. Never exposes credentials or stack traces."
    ),
)
def ready(response: Response, service: KnowledgeService = Depends(get_service)):
    report = service.readiness()
    response.status_code = 200 if report.ready else 503
    return report


@app.post("/escalations")
def create_escalation(
    request: EscalationCreateRequest,
    service: KnowledgeService = Depends(get_service),
):
    return service.create_escalation(request.question, request.reason)


@app.get("/escalations")
def list_escalations(
    limit: int = 100,
    service: KnowledgeService = Depends(get_service),
):
    return {"escalations": service.list_escalations(limit)}


@app.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: str,
    request: EscalationResolveRequest,
    service: KnowledgeService = Depends(get_service),
):
    try:
        return service.resolve_escalation(escalation_id, request.answer, request.reviewer)
    except KeyError:
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "escalation not found"}})


@app.exception_handler(ServiceUnavailable)
async def _service_unavailable_handler(request: Request, exc: ServiceUnavailable):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "service_unavailable",
                "message": "a required dependency is unavailable",
                "detail": f"{exc.dependency}: {exc.message}",
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "the request body failed validation",
            }
        },
    )


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "an unexpected internal error occurred",
            }
        },
    )
