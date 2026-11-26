import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def private_response_headers(request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:
            # Error details can contain SQL parameters, filenames or request content.
            logger.error("Unhandled request error (%s)", type(exc).__name__)
            response = JSONResponse(
                status_code=500,
                content={"code": 50000, "message": "Internal server error", "data": None},
            )
        if request.url.path.startswith(
            (
                "/api/v1/auth/",
                "/api/v1/users/",
                "/api/v1/tasks",
                "/api/v1/focus/",
                "/api/v1/journals",
                "/api/v1/notes",
                "/api/v1/note-folders",
                "/api/v1/documents",
                "/api/v1/schedules",
                "/api/v1/dashboard",
                "/api/v1/problems",
                "/api/v1/statistics",
                "/api/v1/admin",
            )
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-FocusNest-Journal-Access",
            "X-FocusNest-Filename",
        ],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
