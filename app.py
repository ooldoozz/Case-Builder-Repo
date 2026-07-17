from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import Base, engine
from routers import case_router, page_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Case Builder API",
    description="AI-powered Case Study Builder",
    version="0.1.0",
    lifespan=lifespan,
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


