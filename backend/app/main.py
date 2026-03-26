from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.aggregation import router as aggregation_router
from app.api.catalog import router as catalog_router
from app.api.orders import router as orders_router
from app.api.templates import router as templates_router
from app.api.restaurants import router as restaurants_router
from app.api.warehouse import router as warehouse_router
from app.auth.router import router as auth_router
from app.config import settings
from app.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="SupplyFlow API",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(templates_router)
app.include_router(orders_router)
app.include_router(admin_router)
app.include_router(aggregation_router)
app.include_router(restaurants_router)
app.include_router(warehouse_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
