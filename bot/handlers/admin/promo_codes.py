"""
bot/handlers/admin/promo_codes.py — Admin panel uchun promo-kodlarni boshqarish
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from bot.filters.admin import IsAdmin
from db.models.promo_code import PromoCode, PromoCodeUsage
from db.models.setting import SettingKeys
from core.emoji import btn_args

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class PromoAdminStates(StatesGroup):
    waiting_for_code       = State()
    waiting_for_amount     = State()
    waiting_for_max_uses   = State()
    waiting_for_expires    = State()


# ─────────────────────────────────────────────
# PROMO-KODLAR ASOSIY RO'YXAT
# ─────────────────────────────────────────────

async def _show_promo_list(target, session: AsyncSession, edit: bool = False):
    res = await session.execute(
        select(PromoCode).order_by(PromoCode.created_at.desc()).limit(25)
    )
    promos = res.scalars().all()

    now = datetime.now(timezone.utc)
    lines = ["🎟 <b>Promo-kodlar boshqaruvi</b>\n"]
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi promo-kod yaratish", callback_data="adm_promo_create")

    if promos:
        for p in promos:
            exp = f" | ⏳ {p.expires_at.strftime('%d.%m.%Y')}" if p.expires_at else ""
            expired = p.expires_at and now > p.expires_at
            max_u = f"{p.max_uses} ta" if p.max_uses else "∞"
            status_icon = "🔴" if (not p.is_active or expired) else "🟢"
            lines.append(
                f"{status_icon} <code>{p.code}</code> — "
                f"+{int(p.reward_amount):,} so'm | "
                f"{p.current_uses}/{max_u} foydalanilgan{exp}"
            )
            builder.button(
                text=f"{status_icon} {p.code}",
                callback_data=f"adm_promo_view_{p.id}"
            )
    else:
        lines.append("\nHozircha promo-kodlar yo'q.")

    builder.adjust(1)
    text = "\n".join(lines)

    if edit and isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:
            await target.message.answer(text, reply_markup=builder.as_markup())
        await target.answer()
    elif isinstance(target, Message):
        await target.answer(text, reply_markup=builder.as_markup())
    elif isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=builder.as_markup())
        await target.answer()


@router.message(F.text.endswith("Promo-kodlar"))
async def admin_promo_list(message: Message, session: AsyncSession):
    await _show_promo_list(message, session)


@router.callback_query(F.data == "adm_promo_list")
async def admin_promo_list_cb(callback: CallbackQuery, session: AsyncSession):
    await _show_promo_list(callback, session, edit=True)


# ─────────────────────────────────────────────
# BITTA PROMO-KOD KO'RISH / BOSHQARISH
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_promo_view_"))
async def view_promo(callback: CallbackQuery, session: AsyncSession):
    promo_id = int(callback.data.removeprefix("adm_promo_view_"))
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Promo-kod topilmadi!", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    expired = promo.expires_at and now > promo.expires_at
    status_txt = "🔴 Nofaol" if (not promo.is_active or expired) else "🟢 Faol"
    exp_txt = promo.expires_at.strftime("%d.%m.%Y %H:%M UTC") if promo.expires_at else "Cheksiz"
    max_u = f"{promo.max_uses} ta" if promo.max_uses else "Cheksiz"
    uses_res = await session.execute(
        select(PromoCodeUsage).where(PromoCodeUsage.promo_code_id == promo_id)
    )
    usage_count = len(uses_res.scalars().all())

    text = (
        f"🎟 <b>Promo-kod: <code>{promo.code}</code></b>\n\n"
        f"💰 Mukofot: <b>+{int(promo.reward_amount):,} so'm</b>\n"
        f"📊 Holati: {status_txt}\n"
        f"👥 Ishlatilgan: <b>{usage_count}</b> ta (limit: {max_u})\n"
        f"⏳ Amal qilish muddati: <b>{exp_txt}</b>\n"
        f"📅 Yaratilgan: {promo.created_at.strftime('%d.%m.%Y') if promo.created_at else '—'}"
    )

    builder = InlineKeyboardBuilder()
    if promo.is_active and not expired:
        builder.button(text="🔴 Faolsizlashtirish", callback_data=f"adm_promo_toggle_{promo_id}")
    else:
        builder.button(text="🟢 Faollashtirish", callback_data=f"adm_promo_toggle_{promo_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"adm_promo_delete_{promo_id}")
    builder.button(text="↩️ Ro'yxatga qaytish", callback_data="adm_promo_list")
    builder.adjust(2, 1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm_promo_toggle_"))
async def toggle_promo(callback: CallbackQuery, session: AsyncSession):
    promo_id = int(callback.data.removeprefix("adm_promo_toggle_"))
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Topilmadi!", show_alert=True)
        return
    promo.is_active = not promo.is_active
    await session.commit()
    status = "faollashtirildi ✅" if promo.is_active else "faolsizlashtirildi 🔴"
    await callback.answer(f"<code>{promo.code}</code> {status}", show_alert=True)
    await view_promo(callback, session)


@router.callback_query(F.data.startswith("adm_promo_delete_"))
async def delete_promo(callback: CallbackQuery, session: AsyncSession):
    promo_id = int(callback.data.removeprefix("adm_promo_delete_"))
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Topilmadi!", show_alert=True)
        return
    code = promo.code
    await session.delete(promo)
    await session.commit()
    await callback.answer(f"✅ <code>{code}</code> o'chirildi.", show_alert=True)
    await _show_promo_list(callback, session, edit=True)


# ─────────────────────────────────────────────
# YANGI PROMO-KOD YARATISH (STEP BY STEP)
# ─────────────────────────────────────────────

@router.callback_query(F.data == "adm_promo_create")
async def start_create_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromoAdminStates.waiting_for_code)
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="adm_promo_list")

    await callback.message.edit_text(
        "🎟 <b>Yangi promo-kod yaratish</b>\n\n"
        "<b>1/4 — Promo-kod matni:</b>\n"
        "Faqat lotin harflari va raqamlar ishlatilsin.\n"
        "<i>Masalan: YANGIYIL2026, SUMMER50, VIP100</i>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(PromoAdminStates.waiting_for_code, F.text)
async def promo_step_code(message: Message, state: FSMContext):
    code = message.text.strip().upper().replace(" ", "")
    if not code.replace("_", "").isalnum() or len(code) < 3 or len(code) > 30:
        await message.answer(
            "❌ Noto'g'ri format! Faqat lotin harflari va raqamlar, 3–30 ta belgi.\n"
            "Qayta kiriting:"
        )
        return

    await state.update_data(code=code)
    await state.set_state(PromoAdminStates.waiting_for_amount)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="adm_promo_list")
    await message.answer(
        f"✅ Kod: <code>{code}</code>\n\n"
        "<b>2/4 — Mukofot summasi (so'mda):</b>\n"
        "<i>Masalan: 10000, 50000, 100000</i>",
        reply_markup=builder.as_markup()
    )


@router.message(PromoAdminStates.waiting_for_amount, F.text)
async def promo_step_amount(message: Message, state: FSMContext):
    raw = message.text.strip().replace(",", "").replace(" ", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ Faqat musbat raqam kiriting. Qayta:")
        return

    await state.update_data(amount=int(raw))
    await state.set_state(PromoAdminStates.waiting_for_max_uses)

    builder = InlineKeyboardBuilder()
    builder.button(text="♾ Cheksiz (limit yo'q)", callback_data="adm_promo_unlimited")
    builder.button(text="❌ Bekor qilish", callback_data="adm_promo_list")
    builder.adjust(1)

    await message.answer(
        f"✅ Summa: <b>{int(raw):,} so'm</b>\n\n"
        "<b>3/4 — Maksimal foydalanish soni:</b>\n"
        "Necha kishi ishlatishi mumkin? Raqam kiriting yoki 'cheksiz' tanlang.\n"
        "<i>Masalan: 1, 10, 100</i>",
        reply_markup=builder.as_markup()
    )


@router.callback_query(PromoAdminStates.waiting_for_max_uses, F.data == "adm_promo_unlimited")
async def promo_unlimited(callback: CallbackQuery, state: FSMContext):
    await state.update_data(max_uses=None)
    await state.set_state(PromoAdminStates.waiting_for_expires)
    await _ask_expires(callback.message)
    await callback.answer()


@router.message(PromoAdminStates.waiting_for_max_uses, F.text)
async def promo_step_max_uses(message: Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ Faqat musbat butun son kiriting. Qayta:")
        return

    await state.update_data(max_uses=int(raw))
    await state.set_state(PromoAdminStates.waiting_for_expires)
    await _ask_expires(message)


async def _ask_expires(target):
    builder = InlineKeyboardBuilder()
    builder.button(text="♾ Muddatsiz", callback_data="adm_promo_no_expire")
    builder.button(text="📅 1 kun", callback_data="adm_promo_expire_1")
    builder.button(text="📅 7 kun", callback_data="adm_promo_expire_7")
    builder.button(text="📅 30 kun", callback_data="adm_promo_expire_30")
    builder.button(text="❌ Bekor qilish", callback_data="adm_promo_list")
    builder.adjust(1, 3, 1)

    text = (
        "<b>4/4 — Amal qilish muddati:</b>\n"
        "Quyidan tanlang yoki kun sonini kiriting (masalan: 14):"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=builder.as_markup())
    else:
        await target.edit_text(text, reply_markup=builder.as_markup())


async def _finish_promo_creation(target, state: FSMContext, session: AsyncSession, expires_at=None):
    data = await state.get_data()
    await state.clear()

    code = data["code"]
    amount = data["amount"]
    max_uses = data.get("max_uses")

    # Check duplicate
    res = await session.execute(select(PromoCode).where(PromoCode.code == code))
    if res.scalar_one_or_none():
        msg = f"❌ <code>{code}</code> kodi allaqachon mavjud! Boshqa kod tanlang."
        if isinstance(target, Message):
            await target.answer(msg)
        else:
            await target.message.answer(msg)
        return

    promo = PromoCode(
        code=code,
        reward_amount=Decimal(str(amount)),
        max_uses=max_uses,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(promo)
    await session.commit()

    exp_txt = expires_at.strftime("%d.%m.%Y %H:%M UTC") if expires_at else "Muddatsiz"
    max_u_txt = f"{max_uses} ta" if max_uses else "Cheksiz"

    success_text = (
        "✅ <b>Promo-kod muvaffaqiyatli yaratildi!</b>\n\n"
        f"🎟 Kod: <code>{code}</code>\n"
        f"💰 Mukofot: <b>+{amount:,} so'm</b>\n"
        f"👥 Limit: {max_u_txt}\n"
        f"⏳ Muddat: {exp_txt}\n\n"
        "Bu kodni foydalanuvchilarga ulashing!"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Barcha kodlar", callback_data="adm_promo_list")
    builder.button(text="➕ Yana yaratish", callback_data="adm_promo_create")
    builder.adjust(1)

    if isinstance(target, Message):
        await target.answer(success_text, reply_markup=builder.as_markup())
    else:
        await target.message.answer(success_text, reply_markup=builder.as_markup())
        await target.answer()


@router.callback_query(PromoAdminStates.waiting_for_expires, F.data == "adm_promo_no_expire")
async def promo_no_expire(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await _finish_promo_creation(callback, state, session, expires_at=None)


@router.callback_query(PromoAdminStates.waiting_for_expires, F.data.startswith("adm_promo_expire_"))
async def promo_preset_expire(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    days = int(callback.data.removeprefix("adm_promo_expire_"))
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    await _finish_promo_creation(callback, state, session, expires_at=expires_at)


@router.message(PromoAdminStates.waiting_for_expires, F.text)
async def promo_custom_expire(message: Message, state: FSMContext, session: AsyncSession):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ Faqat musbat butun son kiriting (kun soni). Qayta:")
        return
    expires_at = datetime.now(timezone.utc) + timedelta(days=int(raw))
    await _finish_promo_creation(message, state, session, expires_at=expires_at)
