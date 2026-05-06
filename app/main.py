from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app
import time

from app.api import routes_health, routes_predict, routes_simulate
from app.config import settings
from app.db.session import Base, engine
from app.services.surrogate import Surrogate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("solar_dryer")

REQUEST_COUNT = Counter("dryer_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("dryer_request_seconds", "Request latency in seconds", ["path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # dev convenience; prod uses alembic
    Surrogate.get()  # warm load so first request isn't slow
    log.info("startup complete; model_version=%s", settings.model_version)
    yield
    log.info("shutdown")


app = FastAPI(title="Solar Dryer Digital Twin", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(path).observe(elapsed)
    return response


app.include_router(routes_health.router)
app.include_router(routes_predict.router)
app.include_router(routes_simulate.router)
app.mount("/metrics", make_asgi_app())
