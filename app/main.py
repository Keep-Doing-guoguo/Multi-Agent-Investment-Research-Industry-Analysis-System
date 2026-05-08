from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router as research_router


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Investment Research API")
    app.include_router(research_router)
    return app


app = create_app()
