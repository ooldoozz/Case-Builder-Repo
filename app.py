from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import initialize_database, is_database_ready
from routers import case_router, page_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Case Builder API",
    description="AI-powered Case Study Builder",
    version="0.1.0",
    lifespan=lifespan,
    # docs_url=None,
    # redoc_url=None,
    # openapi_url=None,
)


# --------------------------------------------------
# Static Files
# --------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

# --------------------------------------------------
# Jinja Templates
# --------------------------------------------------

templates = Jinja2Templates(directory="templates")

# --------------------------------------------------
# API Routes
# --------------------------------------------------

app.include_router(page_router)
app.include_router(case_router)

# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/ready")
def readiness(response: Response):
    if not is_database_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": "unavailable",
        }

    return {
        "status": "ready",
        "database": "available",
    }
