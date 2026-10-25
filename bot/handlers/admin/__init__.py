from aiogram import Router
from .base import router as base_router
from .orders import router as orders_router
from .balance_requests import router as balance_router
from .settings import router as settings_router
from .products import router as products_router
from .categories import router as categories_router
from .emoji import router as emoji_router
from .broadcast import router as broadcast_router
from .promo_codes import router as promo_router

router = Router()
router.include_router(base_router)
router.include_router(orders_router)
router.include_router(products_router)
router.include_router(categories_router)
router.include_router(balance_router)
router.include_router(settings_router)
router.include_router(emoji_router)
router.include_router(broadcast_router)
router.include_router(promo_router)
