from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.api.v1 import api_router
from src.core.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


def make_app():
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount the uploads directory
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    app.include_router(
        api_router,
    )
    return app


app = make_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9006,
        reload=True,
        timeout_graceful_shutdown=360,
    )
