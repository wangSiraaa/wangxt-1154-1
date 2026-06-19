from app.routers.box import router as box_router
from app.routers.dispatch import router as dispatch_router
from app.routers.weighing import router as weighing_router

__all__ = ["box_router", "dispatch_router", "weighing_router"]
