from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.promo_code import PromoCode, PromoCodeUsage
from db.models.user import User
from db.models.balance_transaction import TransactionType
from services.wallet import credit


class PromoError(Exception):
    pass


async def activate_promo_code(session: AsyncSession, user_id: int, code_raw: str) -> tuple[Decimal, Decimal]:
    """
    Promo kodni faollashtirish.
    Returns: (reward_amount, new_balance)
    Raises: PromoError with user-friendly message
    """
    code_clean = code_raw.strip().upper()
    if not code_clean:
        raise PromoError("Promo-kod kiritilmadi.")

    # 1. SELECT FOR UPDATE on promo_codes to avoid race condition on max_uses / current_uses
    res = await session.execute(
        select(PromoCode).where(PromoCode.code == code_clean).with_for_update()
    )
    promo = res.scalar_one_or_none()
    if not promo:
        raise PromoError("❌ Bunday promo-kod topilmadi!")

    if not promo.is_active:
        raise PromoError("❌ Ushbu promo-kod hozirda faol emas.")

    # 2. Check expiration
    if promo.expires_at:
        now = datetime.now(timezone.utc)
        if now > promo.expires_at:
            raise PromoError("❌ Ushbu promo-kodning amal qilish muddati tugagan.")

    # 3. Check max_uses
    if promo.max_uses and promo.max_uses > 0:
        if promo.current_uses >= promo.max_uses:
            raise PromoError("❌ Ushbu promo-koddan foydalanish limiti tugagan.")

    # 4. Check if user already used this promo code
    usage_res = await session.execute(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo.id,
            PromoCodeUsage.user_id == user_id
        )
    )
    if usage_res.scalar_one_or_none():
        raise PromoError("❌ Siz ushbu promo-koddan allaqachon foydalangansiz!")

    # 5. Record usage
    usage = PromoCodeUsage(promo_code_id=promo.id, user_id=user_id)
    session.add(usage)
    promo.current_uses += 1

    # 6. Credit wallet
    reward = Decimal(str(promo.reward_amount))
    await credit(
        session=session,
        user_id=user_id,
        amount=reward,
        type_=TransactionType.PROMO_CODE,
        ref_type="promo_code",
        ref_id=str(promo.id)
    )

    await session.commit()

    # Get updated balance
    user = await session.get(User, user_id)
    return reward, Decimal(str(user.balance))
