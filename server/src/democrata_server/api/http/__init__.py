from fastapi import APIRouter

from .routes import auth, billing, health, ingestion, orgs, rag

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router)  # prefix /auth defined in router
router.include_router(orgs.router)  # prefix /orgs defined in router
router.include_router(billing.router)  # prefix /billing defined in router
router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
router.include_router(rag.router, prefix="/rag", tags=["rag"])
