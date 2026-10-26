from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Callable

from bot.filters.admin import IsAdmin
from db.models.user import User
from db.models.order import Order, OrderStatus, BalanceRequest, BalanceRequestStatus
from db.models.product import Category, Product
from core.emoji import reply_btn

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def get_admin_keyboard(is_super: bool = True) -> ReplyKeyboardMarkup:
    """Admin panel asosiy klaviaturasi (Bosh admin va oddiy admin uchun)"""
    rows = [
        [reply_btn("stats", "Statistika"),
         reply_btn("users", "Foydalanuvchilar")],
        [reply_btn("products", "Mahsulotlar"),
         reply_btn("categories", "Kategoriyalar")],
        [reply_btn("balance_requests", "Balans so'rovlari"),
         reply_btn("orders", "Buyurtmalar")],
        [reply_btn("broadcast", "Xabar yuborish")],
    ]
    
    # Faqat Bosh admin uchun ko'rinadigan muhim bo'limlar
    if is_super:
        rows.append([reply_btn("settings", "Sozlamalar"), reply_btn("promo_admin", "Promo-kodlar")])
        rows.append([reply_btn("premium", "Premium Emoji"), reply_btn("back_home", "Bosh menyuga")])
    else:
        rows.append([reply_btn("promo_admin", "Promo-kodlar"), reply_btn("back_home", "Bosh menyuga")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(Command("admin"))
@router.message(F.text.endswith("Admin panel"))
async def admin_menu(event: Message | CallbackQuery):
    from core.config import config
    user_id = event.from_user.id
    is_super = int(user_id) == int(config.ADMIN_ID)
    role_text = "👑 Bosh Admin" if is_super else "🛡 Admin"
    txt = f"⚙ <b>Boshqaruv paneli ({role_text})</b>\n\nKerakli bo'limni tanlang:"
    kb = get_admin_keyboard(is_super=is_super)
    
    if isinstance(event, CallbackQuery):
        await event.message.answer(txt, reply_markup=kb)
    else:
        await event.answer(txt, reply_markup=kb)


@router.message(F.text.endswith("Bosh menyuga"))
async def back_to_main(message: Message, _: Callable[[str], str]):
    from bot.handlers.registration import get_main_menu_keyboard
    await message.answer(
        "🏠 <b>Bosh menyuga qaytdingiz.</b>",
        reply_markup=get_main_menu_keyboard(_, is_admin=True)
    )


# ───────────────────────────────────────────
# STATISTIKA (kengaytirilgan)
# ───────────────────────────────────────────

@router.message(F.text.endswith("Statistika"))
async def show_statistics(message: Message, session: AsyncSession):
    from datetime import datetime, timedelta, timezone
    from db.models.stock_item import StockItem, StockItemStatus
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Foydalanuvchilar ──
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    new_today = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= day_ago)
    )).scalar() or 0
    new_week = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )).scalar() or 0
    new_month = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= month_ago)
    )).scalar() or 0

    # ── Buyurtmalar ──
    total_orders = (await session.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED)
    )).scalar() or 0
    orders_today = (await session.execute(
        select(func.count(Order.id)).where(
            Order.status == OrderStatus.COMPLETED, Order.created_at >= day_ago)
    )).scalar() or 0
    orders_week = (await session.execute(
        select(func.count(Order.id)).where(
            Order.status == OrderStatus.COMPLETED, Order.created_at >= week_ago)
    )).scalar() or 0

    # ── Daromad ──
    total_revenue = (await session.execute(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.status == OrderStatus.COMPLETED)
    )).scalar() or 0
    daily_rev = (await session.execute(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.status == OrderStatus.COMPLETED, Order.created_at >= day_ago)
    )).scalar() or 0
    weekly_rev = (await session.execute(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.status == OrderStatus.COMPLETED, Order.created_at >= week_ago)
    )).scalar() or 0
    monthly_rev = (await session.execute(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.status == OrderStatus.COMPLETED, Order.created_at >= month_ago)
    )).scalar() or 0

    # ── Kutayotgan so'rovlar ──
    pending_balance = (await session.execute(
        select(func.count(BalanceRequest.id)).where(
            BalanceRequest.status == BalanceRequestStatus.PENDING)
    )).scalar() or 0

    # ── Mahsulotlar va stock ──
    total_products = (await session.execute(select(func.count(Product.id)))).scalar() or 0
    available_stock = (await session.execute(
        select(func.count(StockItem.id)).where(StockItem.status == StockItemStatus.AVAILABLE)
    )).scalar() or 0

    # ── Top mahsulot ──
    top_prod_res = await session.execute(
        select(Product.name, func.count(Order.id).label("cnt"))
        .join(Order, Order.product_id == Product.id)
        .where(Order.status == OrderStatus.COMPLETED)
        .group_by(Product.name)
        .order_by(func.count(Order.id).desc())
        .limit(1)
    )
    top_row = top_prod_res.first()
    top_product = f"{top_row[0]} ({top_row[1]} ta)" if top_row else "—"

    USD = 12700
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"<blockquote>"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"  • Jami: <b>{total_users}</b>\n"
        f"  • Bugun: <b>+{new_today}</b>\n"
        f"  • Hafta: <b>+{new_week}</b>\n"
        f"  • Oy: <b>+{new_month}</b>\n\n"
        f"🛒 <b>Buyurtmalar:</b>\n"
        f"  • Bugun: <b>{orders_today}</b>\n"
        f"  • Hafta: <b>{orders_week}</b>\n"
        f"  • Jami: <b>{total_orders}</b>\n\n"
        f"💰 <b>Daromadlar:</b>\n"
        f"  • Bugun: <b>{float(daily_rev):,.0f} so'm</b> (${float(daily_rev)/USD:.2f})\n"
        f"  • Hafta: <b>{float(weekly_rev):,.0f} so'm</b> (${float(weekly_rev)/USD:.2f})\n"
        f"  • Oy: <b>{float(monthly_rev):,.0f} so'm</b> (${float(monthly_rev)/USD:.2f})\n"
        f"  • Jami: <b>{float(total_revenue):,.0f} so'm</b> (${float(total_revenue)/USD:.2f})\n\n"
        f"🏆 <b>Top mahsulot:</b> {top_product}\n"
        f"📦 <b>Stokdagi tovarlar:</b> {available_stock}\n"
        f"🛍 <b>Mahsulotlar:</b> {total_products}\n"
        f"⏳ <b>Kutayotgan balans:</b> {pending_balance}"
        f"</blockquote>"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Tranzaksiyalar tarixi", callback_data="adm_tx_history")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "adm_tx_history")
async def show_tx_history(callback: CallbackQuery, session: AsyncSession):
    from db.models.balance_transaction import BalanceTransaction
    res = await session.execute(
        select(BalanceTransaction).order_by(BalanceTransaction.created_at.desc()).limit(15)
    )
    txs = res.scalars().all()

    if not txs:
        await callback.answer("Tranzaksiyalar yo'q.", show_alert=True)
        return

    lines = ["📜 <b>Oxirgi 15 ta tranzaksiya:</b>\n"]
    for tx in txs:
        date = tx.created_at.strftime("%d.%m %H:%M") if tx.created_at else ""
        sign = "+" if tx.amount > 0 else ""
        lines.append(f"• <code>{tx.id}</code> | {date} | {tx.type.value} | {sign}{float(tx.amount):,.0f} so'm | User: {tx.user_id}")

    await callback.message.answer("\n".join(lines))
    await callback.answer()


# ───────────────────────────────────────────
# FOYDALANUVCHILAR (kengaytirilgan)
# ───────────────────────────────────────────

@router.message(F.text.endswith("Foydalanuvchilar"))
async def show_users(message: Message, session: AsyncSession):
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(10)
    )
    users = result.scalars().all()

    total = (await session.execute(select(func.count(User.id)))).scalar() or 0

    if not users:
        await message.answer("👥 Foydalanuvchilar yo'q.")
        return

    lines = [
        f"👥 <b>Foydalanuvchilar</b> (jami: {total})\n<i>Oxirgi 10 ta:</i>\n"]
    for u in users:
        uname = f"@{u.username}" if u.username else "—"
        balance = float(u.balance or 0)
        lines.append(
            f"• {u.first_name or '—'} {uname} — {balance:,.0f} so'm — <code>{u.telegram_id}</code>")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Foydalanuvchi qidirish", callback_data="adm_user_search")
    builder.adjust(1)

    await message.answer("\n".join(lines), reply_markup=builder.as_markup())


from bot.states.admin import AdminUserManage


@router.callback_query(F.data == "adm_user_search")
async def ask_user_search(callback: CallbackQuery, state: FSMContext):
    from aiogram.fsm.context import FSMContext
    await callback.message.answer(
        "🔍 <b>Foydalanuvchi qidirish</b>\n\n"
        "Telegram ID yoki username kiriting:\n"
        "<i>Masalan: <code>123456789</code> yoki <code>ali_dev</code></i>"
    )
    await state.set_state(AdminUserManage.waiting_for_user_id)
    await callback.answer()


@router.message(AdminUserManage.waiting_for_user_id, F.text)
async def search_user(message: Message, state: FSMContext, session: AsyncSession):
    query = message.text.strip().lstrip("@")

    # ID bo'yicha qidirish
    if query.isdigit():
        result = await session.execute(
            select(User).where(User.telegram_id == int(query))
        )
    else:
        result = await session.execute(
            select(User).where(User.username.ilike(f"%{query}%"))
        )

    user = result.scalar_one_or_none()
    await state.clear()

    if not user:
        await message.answer(
            f"❌ <b>Foydalanuvchi topilmadi:</b> <code>{query}</code>\n\n"
            "Qayta qidirish uchun yana urinib ko'ring."
        )
        return

    await _show_user_detail(message, user, session)


async def _show_user_detail(target, user: User, session: AsyncSession):
    """Foydalanuvchi batafsil ma'lumotlarini ko'rsatish"""
    from db.models.order import Order, OrderStatus

    # Xaridlar soni
    orders_cnt = (await session.execute(
        select(func.count(Order.id)).where(
            Order.user_id == user.id, Order.status == OrderStatus.COMPLETED)
    )).scalar() or 0

    total_spent = float(user.total_spent or 0)
    balance = float(user.balance or 0)
    ref_balance = float(user.ref_balance or 0)
    joined = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"
    uname = f"@{user.username}" if user.username else "—"

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"<blockquote>"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"👤 Ism: {user.first_name or '—'}\n"
        f"📱 Username: {uname}\n"
        f"📞 Telefon: {user.phone_number or '—'}\n"
        f"🌐 Til: {user.language or 'uz'}\n"
        f"📅 Ro'yxatdan: {joined}\n\n"
        f"💰 Balans: <b>{balance:,.0f} so'm</b>\n"
        f"🎁 Ref balans: <b>{ref_balance:,.0f} so'm</b>\n"
        f"💸 Jami sarflagan: <b>{total_spent:,.0f} so'm</b>\n"
        f"🛒 Xaridlar: <b>{orders_cnt} ta</b>\n"
        f"🔗 Referal: <code>{user.referral_code or '—'}</code>\n"
        f"📨 Taklif qilgan: {user.referred_by or '—'}"
        f"</blockquote>"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Balans qo'shish", callback_data=f"adm_ubal_add_{user.id}")
    builder.button(text="💸 Balans yechish", callback_data=f"adm_ubal_sub_{user.id}")
    builder.button(text="🚫 Bloklash" if not user.is_blocked else "✅ Blokdan chiqarish",
                   callback_data=f"adm_utoggle_{user.id}")
    builder.button(text="🔍 Boshqa qidirish", callback_data="adm_user_search")
    builder.adjust(2, 1, 1)

    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=builder.as_markup())
        await target.answer()
    else:
        await target.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("adm_ubal_add_"))
async def ask_add_balance(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await callback.message.answer(
        "💰 <b>Qancha miqdor qo'shmoqchisiz?</b>\n\n"
        "Raqamda kiriting (masalan: <code>50000</code>):"
    )
    await state.set_state(AdminUserManage.waiting_for_balance_add)
    await callback.answer()


@router.message(AdminUserManage.waiting_for_balance_add, F.text)
async def process_add_balance(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    uid = data.get("target_user_id")
    raw = message.text.strip().replace(" ", "").replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    amount = int(raw)
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        await state.clear()
        return

    from decimal import Decimal
    user.balance = (user.balance or Decimal("0")) + Decimal(str(amount))
    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ <b>{amount:,} so'm</b> qo'shildi!\n"
        f"Yangi balans: <b>{float(user.balance):,.0f} so'm</b>"
    )


@router.callback_query(F.data.startswith("adm_ubal_sub_"))
async def ask_sub_balance(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    await callback.message.answer(
        "💸 <b>Qancha miqdor yechmoqchisiz?</b>\n\n"
        "Raqamda kiriting (masalan: <code>50000</code>):"
    )
    await state.set_state(AdminUserManage.waiting_for_balance_sub)
    await callback.answer()


@router.message(AdminUserManage.waiting_for_balance_sub, F.text)
async def process_sub_balance(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    uid = data.get("target_user_id")
    raw = message.text.strip().replace(" ", "").replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return

    amount = int(raw)
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi!")
        await state.clear()
        return

    from decimal import Decimal
    user.balance = max(Decimal("0"), (user.balance or Decimal("0")) - Decimal(str(amount)))
    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ <b>{amount:,} so'm</b> yechildi!\n"
        f"Yangi balans: <b>{float(user.balance):,.0f} so'm</b>"
    )


@router.callback_query(F.data.startswith("adm_utoggle_"))
async def toggle_user_block(callback: CallbackQuery, session: AsyncSession):
    user_id = int(callback.data.split("_")[2])
    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    user.is_blocked = not user.is_blocked
    await session.commit()

    status = "🚫 Bloklandi" if user.is_blocked else "✅ Blokdan chiqarildi"
    await callback.answer(f"{status}: {user.first_name or user.telegram_id}", show_alert=True)
    await _show_user_detail(callback, user, session)

