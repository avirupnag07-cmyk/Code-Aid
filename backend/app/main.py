"""Application factory and ASGI entry point for Code-Aid."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings
from .db import InvestigationRepository
from .engine.ingestion import IngestionLimits, SampleCatalog
from .api.routes import create_router


def create_app(settings: Settings = None) -> FastAPI:
    configured = settings or Settings.from_env()
    configured.storage_dir.mkdir(parents=True, exist_ok=True)
    repository = InvestigationRepository(configured)
    catalog = SampleCatalog(
        configured.samples_dir,
        IngestionLimits(
            max_members=configured.max_archive_members,
            max_uncompressed_bytes=configured.max_archive_uncompressed_bytes,
            max_member_bytes=configured.max_archive_member_bytes,
            max_source_file_bytes=configured.max_source_file_bytes,
        ),
    )
    application = FastAPI(
        title="Code-Aid Backend API",
        version=__version__,
        description="Safe, deterministic traceback investigation for Python projects.",
    )
    application.state.settings = configured
    application.state.repository = repository
    application.state.catalog = catalog
    origins = list(configured.allowed_origins)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    router = create_router(configured, repository, catalog)
    # /api is the documented contract. Root aliases keep a simple React dev
    # proxy configuration possible without changing the backend behavior.
    application.include_router(router, prefix="/api")
    application.include_router(router)
    return application


app = create_app()
