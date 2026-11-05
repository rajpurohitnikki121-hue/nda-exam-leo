from aiogram import Router
from .start import router as start_router
from .quiz_flow import router as quiz_flow_router
from .admin_broadcast import router as admin_broadcast_router
from .stats import router as stats_router
from .nda_exam import router as nda_router


def setup_routers() -> Router:
    """Combines all modular routers under a root router."""
    root_router = Router(name="root_router")
    root_router.include_router(start_router)
    root_router.include_router(nda_router)
    root_router.include_router(admin_broadcast_router)
    root_router.include_router(stats_router)
    root_router.include_router(quiz_flow_router)
    return root_router


__all__ = [
    "setup_routers",
    "start_router",
    "quiz_flow_router",
    "admin_broadcast_router",
    "stats_router",
    "nda_router",
]
