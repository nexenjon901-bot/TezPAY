from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models.user import User
from core.config import config
from core.emoji import pe, btn_args

router = Router()


from core.utils import format_money
from services.wallet import credit, TransactionType
from db.models.setting import Setting, SettingKeys

DEFAULT_MIN_WITHDRAWAL = 10000

async def _get_min_withdrawal(session):
    res = await session.execute(select(Setting).where(Setting.key == SettingKeys.MIN_WITHDRAWAL))
    s = res.scalar_one_or_none()
    try:
        return float(s.value) if s else DEFAULT_MIN_WITHDRAWAL
    except Exception:
        return DEFAULT_MIN_WITHDRAWAL

async def _get_setting_val(session, key, default):
    res = await session.execute(select(Setting).where(Setting.key == key))
    s = res.scalar_one_or_none()
    return s.value if s else default

@router.callback_query(F.data == "ref_withdraw")
async def withdraw_referral_bonus(callback: CallbackQuery, session: AsyncSession, db_user: User):
    if not db_user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    min_wd = await _get_min_withdrawal(session)
    ref_bal = float(db_user.ref_balance or 0)
    if ref_bal < min_wd:
        await callback.answer(f"❌ Minimal yechib olish summasi {format_money(min_wd)}!\nSizda: {format_money(ref_bal)}", show_alert=True)
        return
        
    # Atomik ravishda o'tkazish
    from sqlalchemy import text
    res = await session.execute(
        text("UPDATE users SET ref_balance = 0 WHERE id = :uid AND ref_balance >= :min_amt RETURNING ref_balance"),
        {"uid": db_user.id, "min_amt": min_wd}
    )
    row = res.fetchone()
    if not row:
        await callback.answer("❌ Xatolik! Balans yetarli emas.", show_alert=True)
        return
        
    withdrawn = row[0]
    
    # Asosiy balansga qo'shish
    from decimal import Decimal
    await credit(session, db_user.id, Decimal(str(withdrawn)), TransactionType.REFERRAL_BONUS, ref_type="withdrawal", ref_id=str(db_user.id))
    await session.commit()
    
    await callback.answer(f"✅ {format_money(withdrawn)} asosiy balansingizga o'tkazildi!", show_alert=True)
    
    # Sahifani yangilash
    await session.refresh(db_user)
    await show_referral(callback.message, session, db_user)

import urllib.parse

async def show_referral(message: Message, session: AsyncSession, db_user: User):
    if not db_user:
        await message.answer("❌ Avval ro'yxatdan o'ting: /start")
        return

    if not db_user.referral_code:
        await message.answer("❌ Referal kodingiz mavjud emas. /start bosing.")
        return

    # Referallar soni
    ref_result = await session.execute(
        select(func.count(User.id)).where(User.referred_by == db_user.referral_code)
    )
    ref_count = ref_result.scalar() or 0

    # Dinamik sozlamalar
    min_wd = await _get_min_withdrawal(session)
    bonus_amount = getattr(config, "REFERRAL_BONUS_UZS", 500)
    ref_bal = float(db_user.ref_balance or 0)

    bot_username = config.BOT_USERNAME
    ref_link = f"https://t.me/{bot_username}?start={db_user.referral_code}"
    share_text = urllib.parse.quote("🎮 PUBG Mobile va o'yin akkauntlari do'koni! Tezkor va ishonchli xarid qiling:")
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    # Screenshot 4 uslubidagi blockquote va statistika
    text = (
        f"{pe('referral')} <b>Referal tizimi</b>\n\n"
        f"<blockquote>"
        f"Taklif havolangiz orqali do'stlaringizni taklif qiling va har bir "
        f"do'stingiz uchun {bonus_amount:,} so'm hisobingizga oling!\n\n"
        f"🔗 Sizning taklif havolangiz:\n"
        f"{ref_link}\n\n"
        f"{pe('stats')} Statistikangiz:\n"
        f"• Jami takliflar: {ref_count} ta\n"
        f"• Tasdiqlangan: {ref_count} ta\n"
        f"• Ishlangan summa: {ref_bal:,.0f} so'm"
        f"</blockquote>\n\n"
        f"🛡️ <i>Har bir do'stingiz xavfsizlik tekshiruvidan o'tgach hisobingizga bonus beriladi.</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("share", "Do'stlarga ulashish"), url=share_url)
    if ref_bal >= min_wd:
        builder.button(**btn_args("money", "Asosiy balansga o'tkazish"), callback_data="ref_withdraw")
    
    builder.button(**btn_args("back", "Orqaga"), callback_data="menu_back_main")
    builder.adjust(1)

    banner_exists = os.path.exists(REFERRAL_BANNER)

    if isinstance(message, CallbackQuery):
        try:
            await message.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:
            await message.message.answer(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "menu_back_main")
async def ref_back_main(callback: CallbackQuery):
    from bot.handlers.registration import get_main_menu_keyboard
    from core.config import config
    is_admin = callback.from_user.id in config.all_admin_ids
    first_name = callback.from_user.first_name or "Foydalanuvchi"
    text = (
        f"{pe('welcome')} <b>Assalomu alaykum, {first_name}!</b>\n\n"
        f"<blockquote>"
        f"Do'konimizga xush kelibsiz! O'zingizga ma'qul bo'limni tanlang va qulay xarid qiling."
        f"</blockquote>"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=get_main_menu_keyboard(lambda x: x, is_admin=is_admin))
    except Exception:
        await callback.message.answer(text, reply_markup=get_main_menu_keyboard(lambda x: x, is_admin=is_admin))
    await callback.answer()
