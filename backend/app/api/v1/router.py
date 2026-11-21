"""API v1 router registry aggregating all domain module routers (SDD-2 Section 4)."""

from fastapi import APIRouter

from app.modules.ai.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.auth.router import router as auth_router
from app.modules.collection_orders.router import router as collection_orders_router
from app.modules.delivery_orders.router import router as delivery_orders_router
from app.modules.equipment_units.router import router as equipment_units_router
from app.modules.items.router import router as items_router
from app.modules.projects.router import router as projects_router
from app.modules.reconciliation.router import router as reconciliation_router
from app.modules.stock_balances.router import router as stock_balances_router
from app.modules.stock_movements.router import router as stock_movements_router
from app.modules.users.router import org_router as organizations_router
from app.modules.users.router import router as users_router
from app.modules.workshop.router import router as workshop_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(items_router)
api_v1_router.include_router(equipment_units_router)
api_v1_router.include_router(stock_balances_router)
api_v1_router.include_router(delivery_orders_router)
api_v1_router.include_router(collection_orders_router)
api_v1_router.include_router(workshop_router)
api_v1_router.include_router(stock_movements_router)
api_v1_router.include_router(reconciliation_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(ai_router)
