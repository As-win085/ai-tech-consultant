from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import AskRequest, AskResponse, ErrorResponse, ReadyReport
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
