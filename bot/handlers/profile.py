from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone
from typing import Callable
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

from db.models.user import User
from db.models.order import Order, OrderStatus
from core.emoji import pe, btn_args

router = Router()

PROFILE_BANNER = "bot/images/profile.png"


async def _build_profile_text(db_user: User, session: AsyncSession) -> str:
    """Profil ma'lumotlarini matn sifatida yaratish — storechookie_bot uslubi"""
    now = datetime.now(timezone.utc)

    # Xaridlar statistikasi
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    # 24 soat
    r24 = await session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.price), 0))
        .where(Order.user_id == db_user.id, Order.status == OrderStatus.COMPLETED, Order.created_at >= day_ago)
    )
    cnt24, sum24 = r24.one()

    # 7 kun
    r7 = await session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.price), 0))
        .where(Order.user_id == db_user.id, Order.status == OrderStatus.COMPLETED, Order.created_at >= week_ago)
    )
    cnt7, sum7 = r7.one()

    # Barcha vaqt
    rall = await session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.price), 0))
        .where(Order.user_id == db_user.id, Order.status == OrderStatus.COMPLETED)
    )
    cntall, sumall = rall.one()

    balance = float(db_user.balance or 0)
    total_spent = float(db_user.total_spent or 0)
    username = f"@{db_user.username}" if db_user.username else "—"
    joined = db_user.created_at.strftime(
        "%b %d, %Y") if db_user.created_at else "—"

    # USD kurs (taxminiy, sozlash mumkin)
    USD_RATE = 12700
    balance_usd = balance / USD_RATE
    spent_usd = total_spent / USD_RATE

    text = (
        f"{pe('profile')} <b>Sizning profilingiz</b>\n\n"
        f"<blockquote>"
        f"🆔 Telegram ID: <code>{db_user.telegram_id}</code>\n"
        f"👤 Username: {username}\n"
        f"📅 Ro'yxatdan o'tgan: {joined}\n\n"
        f"💰 Balans: <b>{balance:,.0f} so'm</b> (${balance_usd:.2f})\n"
        f"💸 Jami xaridlar: <b>{total_spent:,.0f} so'm</b> (${spent_usd:.2f})\n\n"
        f"📊 Xaridlar statistikasi:\n"
        f"• 24 soatda: {cnt24} ta (${float(sum24)/USD_RATE:.2f})\n"
        f"• 7 kunda: {cnt7} ta (${float(sum7)/USD_RATE:.2f})\n"
        f"• Umumiy: {cntall} ta (${float(sumall)/USD_RATE:.2f})"
        f"</blockquote>"
    )
    return text


def _get_profile_keyboard() -> object:
    """Profil sahifasi uchun inline klaviatura — storechookie_bot uslubi"""
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("history", "Buyurtmalar tarixi"), callback_data="profile_orders")
    builder.button(**btn_args("gift", "Promo-kod / Chegirmalar"), callback_data="profile_discounts")
    builder.button(**btn_args("lang", "Bot tili"),             callback_data="profile_change_lang")
    builder.button(**btn_args("back", "Orqaga"),               callback_data="profile_back")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


# ───────────────────────────────────────────
# PROFIL — Ko'rsatish
# ───────────────────────────────────────────

async def show_profile(target, session: AsyncSession, db_user: User):
    if not db_user:
        if isinstance(target, CallbackQuery):
            await target.answer("❌ Avval ro'yxatdan o'ting: /start", show_alert=True)
        else:
            await target.answer("❌ Avval ro'yxatdan o'ting: /start")
        return

    text = await _build_profile_text(db_user, session)
    keyboard = _get_profile_keyboard()

    banner = FSInputFile(PROFILE_BANNER) if os.path.exists(PROFILE_BANNER) else None
    from aiogram.types import InputMediaPhoto

    if isinstance(target, CallbackQuery):
        try:
            if banner:
                await target.message.edit_media(
                    media=InputMediaPhoto(media=banner, caption=text, parse_mode="HTML"),
                    reply_markup=keyboard
                )
            else:
                await target.message.edit_caption(caption=text, reply_markup=keyboard)
        except Exception:
            try:
                await target.message.edit_text(text=text, reply_markup=keyboard)
            except Exception:
                if banner:
                    await target.message.answer_photo(photo=banner, caption=text, reply_markup=keyboard)
                else:
                    await target.message.answer(text, reply_markup=keyboard)
    elif isinstance(target, Message):
        if banner:
            await target.answer_photo(photo=banner, caption=text, reply_markup=keyboard)
        else:
            await target.answer(text, reply_markup=keyboard)


# ───────────────────────────────────────────
# PROFIL — Inline tugmalar
# ───────────────────────────────────────────

@router.callback_query(F.data == "profile_orders")
async def show_orders_history(callback: CallbackQuery, session: AsyncSession, db_user: User):
    result = await session.execute(
        select(Order)
        .where(Order.user_id == db_user.id)
        .order_by(Order.created_at.desc())
        .limit(10)
    )
    orders = result.scalars().all()

    builder = InlineKeyboardBuilder()

    if not orders:
        text = (
            "📋 <b>Buyurtmalar tarixi</b>\n\n"
            "<blockquote>"
            "Siz hali hech narsa xarid qilmadingiz.\n"
            "Do'kon bo'limidan kerakli mahsulotni tanlang."
            "</blockquote>"
        )
    else:
        lines = [
            "📋 <b>Buyurtmalar tarixi</b>\n\n"
            "<blockquote>"
            "Batafsil ma'lumotni ko'rish uchun kerakli buyurtma tugmasini bosing:"
            "</blockquote>\n"
        ]
        for o in orders:
            date = o.created_at.strftime("%d.%m.%Y") if o.created_at else "—"
            status_icons = {
                "COMPLETED": "✅", "CANCELLED": "❌", "REJECTED": "❌",
                "PAYMENT_REVIEW": "⏳", "APPROVED": "✔️", "PENDING_PAYMENT": "⏳",
                "DELIVERY_FAILED": "⚠️"
            }
            icon = status_icons.get(o.status.value if o.status else "", "❓")
            lines.append(f"{icon} <code>{o.order_number}</code> | {float(o.price):,.0f} so'm | {date}")
            
            # Add button for this order
            builder.button(text=f"{icon} #{o.order_number}", callback_data=f"order_view_{o.id}")
            
        text = "\n".join(lines)

    # Adjust order buttons 1 per row for clear mobile tapping
    builder.adjust(1)
    # Add back button on its own row
    builder.row(InlineKeyboardBuilder().button(**btn_args("back", "Orqaga"), callback_data="profile_back_detail").as_markup().inline_keyboard[0])

    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("order_view_"))
async def view_order_details(callback: CallbackQuery, session: AsyncSession, db_user: User):
    order_id = int(callback.data.split("_")[2])
    
    order = await session.get(Order, order_id)
    if not order or order.user_id != db_user.id:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return
        
    from sqlalchemy import text
    from core.security import decrypt_text
    from core.utils import format_money
    from db.models.product import Product
    
    # Mahsulot nomini olish
    prod_name = "Mahsulot"
    if order.product_id:
        prod = await session.get(Product, order.product_id)
        if prod:
            prod_name = prod.name
            
    res = await session.execute(
        text("SELECT data_encrypted FROM stock_items WHERE order_id = :oid"),
        {"oid": order_id}
    )
    row = res.fetchone()
    
    if row and row[0]:
        try:
            item_data = decrypt_text(row[0])
        except Exception:
            item_data = str(row[0])
    else:
        item_data = "Ma'lumot topilmadi yoki yetkazib berilgan."
        
    order_date = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "—"
    
    status_icons = {
        "COMPLETED": "✅ Bajarildi", "CANCELLED": "❌ Bekor qilingan", "REJECTED": "❌ Rad etilgan",
        "PAYMENT_REVIEW": "⏳ Tekshirilmoqda", "APPROVED": "✔️ Tasdiqlangan", "PENDING_PAYMENT": "⏳ Kutilmoqda",
        "DELIVERY_FAILED": "⚠️ Yetkazishda xatolik"
    }
    st_title = status_icons.get(order.status.value if order.status else "", "Holat: " + str(order.status))

    text_msg = (
        f"🧾 <b>Buyurtma #{order.order_number}</b>\n\n"
        f"<blockquote>"
        f"🎮 Mahsulot: <b>{prod_name}</b>\n"
        f"💰 Narxi: <b>{format_money(order.price)}</b>\n"
        f"📊 Holati: <b>{st_title}</b>\n"
        f"📅 Sana: <b>{order_date}</b>\n\n"
        f"🔑 <b>Hisob ma'lumotlari:</b>\n"
        f"<code>{item_data}</code>"
        f"</blockquote>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("back", "Orqaga"), callback_data="profile_orders")
    builder.adjust(1)
    
    try:
        await callback.message.edit_caption(caption=text_msg, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.edit_text(text=text_msg, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "profile_discounts")
async def show_discounts(callback: CallbackQuery):
    text = (
        "🎁 <b>Chegirmalar va Promo-kodlar</b>\n\n"
        "Kanalimizda e'lon qilingan yoki do'stingiz bergan promo-kod orqali balansingizga bepul mablag' olishingiz mumkin!\n\n"
        "Promo-kodni faollashtirish uchun quyidagi tugmani bosing:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("gift", "🎟 Promo-kod kiritish"), callback_data="enter_promo_code")
    builder.button(**btn_args("back", "Orqaga"), callback_data="profile_back_detail")
    builder.adjust(1)

    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "profile_change_lang")
async def ask_language_change(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("lang", "O'zbek tili"), callback_data="setlang_uz")
    builder.button(**btn_args("lang", "Русский"),     callback_data="setlang_ru")
    builder.button(**btn_args("lang", "English"),     callback_data="setlang_en")
    builder.button(**btn_args("back", "Orqaga"),       callback_data="profile_back_detail")
    builder.adjust(1)

    try:
        await callback.message.edit_caption(
            caption="🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>",
            reply_markup=builder.as_markup()
        )
    except Exception:
        await callback.message.edit_text(
            text="🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>",
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("setlang_"))
async def set_language(callback: CallbackQuery, session: AsyncSession, db_user: User):
    lang = callback.data.split("_")[1]
    db_user.language = lang
    await session.commit()

    confirms = {
        "uz": "✅ Til o'zgartirildi: 🇺🇿 O'zbek",
        "ru": "✅ Язык изменён: 🇷🇺 Русский",
        "en": "✅ Language changed: 🇬🇧 English",
    }
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("back", "Profilga qaytish"),
                   callback_data="profile_back_detail")
    builder.adjust(1)

    try:
        await callback.message.edit_caption(caption=confirms[lang], reply_markup=builder.as_markup())
    except Exception:
        await callback.message.edit_text(text=confirms[lang], reply_markup=builder.as_markup())


@router.callback_query(F.data == "profile_back_detail")
async def profile_back_to_detail(callback: CallbackQuery, session: AsyncSession, db_user: User):
    text = await _build_profile_text(db_user, session)
    keyboard = _get_profile_keyboard()
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "profile_back")
async def profile_back_main(callback: CallbackQuery):
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
        await callback.message.edit_caption(caption=text, reply_markup=get_main_menu_keyboard(lambda x: x, is_admin=is_admin))
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=get_main_menu_keyboard(lambda x: x, is_admin=is_admin))
    await callback.answer()
