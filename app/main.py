from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.oecd import router as oecd_router
from app.core.config import settings
from app.core.logging import logger
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
    await engine.dispose()
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title="MarketMind OECD API",
    description=(
        "Microservice for consuming OECD public data via SDMX API. "
        "This service does NOT calculate MOS, Entropy Weight, TOPSIS, or use LLMs. "
        "It exclusively discovers datasets, collects OECD data, normalizes it, "
        "and stores it in PostgreSQL for auditing, traceability and future analysis."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health_router, tags=["Health"])
app.include_router(oecd_router, tags=["OECD"])
