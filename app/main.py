from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import box_router, dispatch_router, weighing_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="环卫压缩站垃圾转运管理系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(box_router)
app.include_router(dispatch_router)
app.include_router(weighing_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def run_server():
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run_server()
