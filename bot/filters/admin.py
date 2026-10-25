from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union
from core.config import config


class IsAdmin(BaseFilter):
    """Bosh admin yoki ikkinchi admin ekanligini tekshirish"""
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return event.from_user.id in config.all_admin_ids


class IsSuperAdmin(BaseFilter):
    """Faqat Bosh admin (Super Admin) uchun filtr"""
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return event.from_user.id == config.ADMIN_ID
