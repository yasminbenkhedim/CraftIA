from fastapi import APIRouter
from app.api.endpoints import jobs, artifacts, auth, credits, brand_kit, presentation_api, video_api, advisory_api, dashboard_api, mcp_api
from app.api.v1 import production, autonomous

api_router = APIRouter()

api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["Artifacts"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
# Mounted at /me so the balance reads as GET /api/me/credits. The admin route inside
# this router is gated on CREDITS_ADMIN_TOKEN and 404s when that is unset.
api_router.include_router(credits.router, prefix="/me", tags=["Credits"])
api_router.include_router(brand_kit.router, prefix="/me", tags=["Brand Kit"])
api_router.include_router(presentation_api.router, prefix="/v1/presentation", tags=["Presentation"])
api_router.include_router(video_api.router, prefix="/v1/video", tags=["Video"])
api_router.include_router(advisory_api.router, prefix="/v1/advisory", tags=["Post-Production Advisory"])
api_router.include_router(dashboard_api.router, prefix="/v1/dashboard", tags=["Dashboard & Analytics"])
api_router.include_router(autonomous.router, prefix="/v1/autonomous", tags=["Autonomous Platform"])
api_router.include_router(production.router, prefix="/v1/production", tags=["Production Control"])
api_router.include_router(mcp_api.router, prefix="/v1/mcp", tags=["Model Context Protocol"])

