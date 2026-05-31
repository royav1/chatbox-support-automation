from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat_routes import router as chat_router
from app.api.email_routes import router as email_router
from app.api.usage_routes import router as usage_router
from app.api.tenant_routes import router as tenant_router

from app.storage.usage_event_log import init_usage_db
from app.tenants.tenant_registry import bootstrap_tenant_registry

logger = logging.getLogger("chatbox")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup logic ----
    try:
        init_usage_db()
        logger.info("usage_db_init_ok")
    except Exception as e:
        # Don't block the API if the usage DB can't initialize (path/permissions).
        logger.exception(f"usage_db_init_failed err={e}")

    try:
        loaded = bootstrap_tenant_registry()
        logger.info(f"tenant_registry_bootstrap_ok loaded={loaded}")
    except Exception as e:
        logger.exception(f"tenant_registry_bootstrap_failed err={e}")

    yield

    # ---- Shutdown logic (optional future cleanup) ----
    # (nothing needed right now)


app = FastAPI(
    title="Chatbox Support API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Go to /docs or /health"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(email_router, prefix="/api", tags=["email"])
app.include_router(usage_router, prefix="/api", tags=["usage"])
app.include_router(tenant_router, prefix="/api", tags=["tenants"])
