from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan 事件处理器：启动时预热服务"""
    from services.embedding_service import get_embedding_service
    from storage.chroma_client import get_vector_store
    get_embedding_service()
    get_vector_store()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
