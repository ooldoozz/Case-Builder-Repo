from contextlib import asynccontextmanager
from fastapi import FastAPI

from database import Base, engine
from routers import case_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Case Builder API",
    description="AI-powered Product Design Case Study Builder",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "message": "Case Builder API is running."
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


app.include_router(case_router)