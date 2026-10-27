from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Callable

from bot.states.balance import BalanceFill
from core.logger import logger
from db.models.user import User
from db.models.order import BalanceRequest
from core.config import config
from core.emoji import pe, btn_args

router = Router()

MIN_AMOUNT = 10_000  # Minimal to'lov (UZS)


async def _send_balance_menu(target, text: str, keyboard):
    """Xabar yuborish (rasmsiz, toza matn)"""
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:  # CallbackQuery
        try:
            await target.message.edit_text(text=text, reply_markup=keyboard)
        except Exception:
            try:
                await target.message.edit_caption(caption=text, reply_markup=keyboard)
            except Exception:
                await target.message.answer(text, reply_markup=keyboard)


# ───────────────────────────────────────────
# BALANS TO'LDIRISH — Asosiy
# ───────────────────────────────────────────

async def show_balance_menu(message: Message, db_user: User):
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("card", "Karta orqali (Chek yuborish)"),
                   callback_data="balance_card_receipt")
    builder.button(**btn_args("gift", "Promo-kod orqali to'ldirish"),
                   callback_data="enter_promo_code")
    builder.button(**btn_args("back", "Orqaga"), callback_data="balance_back")
    builder.adjust(1)

    text = (
        f"{pe('balance')} <b>Balansni to'ldirish</b>\n\n"
        f"<blockquote>"
        f"💳 Joriy balansingiz: <b>{float(db_user.balance or 0):,.0f} so'm</b>\n"
        f"⚠️ Minimal to'lov: <b>{MIN_AMOUNT:,} so'm</b>\n\n"
        f"Hisobingizni karta orqali yoki promo-kod faollashtirib to'ldirishingiz mumkin."
        f"</blockquote>\n\n"
        f"<i>To'lov usulini tanlang:</i>"
    )

    await _send_balance_menu(message, text, builder.as_markup())


# ───────────────────────────────────────────
# KARTA ORQALI — Chek yuborish oqimi
# ───────────────────────────────────────────

@router.callback_query(F.data == "balance_card_receipt")
async def ask_balance_amount(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data="balance_back")
    builder.adjust(1)

    text = (
        f"💰 <b>Balansni to'ldirish</b>\n\n"
        f"💳 <b>Karta orqali (Chek yuborish)</b>\n\n"
        f"Qancha miqdorda to'ldirmoqchisiz?\n"
        f"Minimal miqdor: <b>{MIN_AMOUNT:,} so'm</b>\n\n"
        f"Miqdorni raqamda kiriting (masalan: <code>50000</code>):"
    )

    try:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())

    await state.set_state(BalanceFill.waiting_for_amount)
    await callback.answer()


@router.message(BalanceFill.waiting_for_amount, F.text)
async def process_balance_amount(message: Message, state: FSMContext, session: AsyncSession):
    text_raw = message.text.replace(" ", "").replace(",", "")
    if not text_raw.isdigit():
        await message.answer("❌ Iltimos, faqat raqam kiriting!\nMasalan: <code>50000</code>")
        return

    amount = int(text_raw)
    if amount < MIN_AMOUNT:
        await message.answer(f"❌ Minimal to'lov miqdori: <b>{MIN_AMOUNT:,} so'm</b>\nBoshqa miqdor kiriting:")
        return

    await state.update_data(amount=amount)

    # Karta ma'lumotlarini DB dan olish
    from db.models.setting import Setting, SettingKeys
    card_res = await session.execute(select(Setting).where(Setting.key == SettingKeys.PAYMENT_CARD))
    card_obj = card_res.scalar_one_or_none()
    card_number = card_obj.value if card_obj else config.PAYMENT_CARD

    owner_res = await session.execute(select(Setting).where(Setting.key == SettingKeys.PAYMENT_CARD_OWNER))
    owner_obj = owner_res.scalar_one_or_none()
    card_owner = owner_obj.value if owner_obj else config.PAYMENT_CARD_OWNER

    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data="balance_cancel_state")
    builder.adjust(1)

    text = (
        f"{pe('money')} <b>Balansni to'ldirish</b>\n\n"
        f"<blockquote>"
        f"{pe('card_post')} <b>Karta raqami:</b>\n"
        f"<code>{card_number}</code>\n"
        f"{pe('profile')} <b>Karta egasi:</b> {card_owner}\n\n"
        f"{pe('balance')} <b>To'lanadigan summa:</b> {amount:,} so'm\n"
        f"</blockquote>\n\n"
        f"{pe('star')} <b>To'lov tartibi:</b>\n"
        f"1. Yuqoridagi karta raqamini nusxalab oling.\n"
        f"2. Payme, Click yoki bank ilovangiz orqali <b>{amount:,} so'm</b> o'tkazing.\n"
        f"3. To'lov amalga oshirilgach, <b>to'lov chekini (screenshot yoki PDF)</b> shu yerga yuboring."
    )

    await message.answer(text, reply_markup=builder.as_markup())

    await state.set_state(BalanceFill.waiting_for_receipt)


@router.message(BalanceFill.waiting_for_receipt, F.photo | F.document)
async def process_balance_receipt(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    data = await state.get_data()
    amount = data.get("amount", 0)

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    # BalanceRequest yaratish
    req = BalanceRequest(
        user_id=db_user.id,
        amount_uzs=amount,
        receipt_file_id=file_id,
    )
    session.add(req)
    await session.commit()

    await state.clear()

    text = (
        f"✅ <b>To'lov cheki qabul qilindi!</b>\n\n"
        f"<blockquote>"
        f"💰 Kiritilgan summa: <b>{amount:,} so'm</b>\n"
        f"⏳ Holat: Tekshirilmoqda\n\n"
        f"Administrator to'lovni tekshirib, tez orada balansingizni to'ldiradi. "
        f"Hisobingiz to'ldirilganda sizga avtomatik xabar keladi."
        f"</blockquote>"
    )
    await message.answer(text)

    # Admin ga xabar yuborish
    buyer = f"@{db_user.username}" if db_user.username else f"ID: {db_user.telegram_id}"
    admin_text = (
        f"💰 <b>YANGI BALANS SO'ROVI</b>\n\n"
        f"👤 Foydalanuvchi: {buyer}\n"
        f"💵 Miqdor: <b>{amount:,} so'm</b>\n"
        f"🔑 So'rov ID: #{req.id}\n\n"
        f"Tasdiqlash yoki rad etish uchun admin panelga o'ting."
    )
    from aiogram import Bot
    bot: Bot = message.bot
    try:
        admin_builder = InlineKeyboardBuilder()
        admin_builder.button(**btn_args("confirm", "Tasdiqlash"),
                             callback_data=f"bal_approve_{req.id}")
        admin_builder.button(**btn_args("cancel", "Rad etish"),
                             callback_data=f"bal_reject_{req.id}")
        admin_builder.adjust(2)

        if file_id and message.photo:
            await bot.send_photo(
                config.ADMIN_ID,
                photo=file_id,
                caption=admin_text,
                reply_markup=admin_builder.as_markup()
            )
        else:
            await bot.send_message(config.ADMIN_ID, admin_text, reply_markup=admin_builder.as_markup())
    except Exception:
        logger.exception("Failed to send balance request notification to admin")


@router.callback_query(F.data == "balance_back")
async def balance_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
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


@router.callback_query(F.data == "balance_cancel_state")
async def balance_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("❌ Bekor qilindi.")
