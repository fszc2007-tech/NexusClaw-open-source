from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router_real import api_router_real
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME}-real",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def healthcheck() -> dict:
        return {"status": "ok", "app": f"{settings.APP_NAME}-real"}

    app.include_router(api_router_real, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
