"""
bot/handlers/admin/emoji.py — Admin panelda barcha keyboard va post Premium Emoji IDlarini boshqarish
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.filters.admin import IsAdmin
from db.models.setting import Setting, SettingKeys
from core.emoji import pe, set_emoji, remove_emoji, get_all_emojis, _FALLBACK

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ─────────────────────────────────────────────
# Kategoriya bo'yicha emoji slotlari
# ─────────────────────────────────────────────
EMOJI_CATEGORIES = {
    "main": {
        "title": "📱 Klient: Asosiy menyu tugmalari",
        "slots": [
            (SettingKeys.EMOJI_SHOP,     "Do'kon",              "🛍️"),
            (SettingKeys.EMOJI_PROFILE,  "Profil",              "👤"),
            (SettingKeys.EMOJI_BALANCE,  "Balans to'ldirish",    "💰"),
            (SettingKeys.EMOJI_USEFUL,   "Foydali",             "📄"),
            (SettingKeys.EMOJI_REFERRAL, "Referal tizimi",      "🤝"),
            (SettingKeys.EMOJI_SUPPORT,  "Qo'llab-quvvatlash",  "🧑‍💻"),
            (SettingKeys.EMOJI_ADMIN,    "Admin panel",         "⚙️"),
        ]
    },
    "inner": {
        "title": "🛍️ Klient: Barcha ichki tugmalar",
        "slots": [
            (SettingKeys.EMOJI_BACK,     "Orqaga",              "↩️"),
            (SettingKeys.EMOJI_CART,     "Sotib olish / Savat", "🛒"),
            (SettingKeys.EMOJI_CONFIRM,  "Tasdiqlash",          "✅"),
            (SettingKeys.EMOJI_CANCEL,   "Bekor qilish",        "❌"),
            (SettingKeys.EMOJI_CATEGORY, "Kategoriya belgisi",  "🎮"),
            (SettingKeys.EMOJI_PRODUCT,  "Mahsulot belgisi",    "🎮"),
            (SettingKeys.EMOJI_CARD,     "Karta orqali to'lov", "💳"),
            (SettingKeys.EMOJI_HISTORY,  "Buyurtmalar tarixi",  "📋"),
            (SettingKeys.EMOJI_GIFT,     "Chegirmalar",         "🎁"),
            (SettingKeys.EMOJI_PROMO,    "Promo-kod kiritish",  "🎟"),
            (SettingKeys.EMOJI_LANG,     "Bot tili / Til",      "🌐"),
            (SettingKeys.EMOJI_SHARE,    "Do'stlarga ulashish", "📲"),
            (SettingKeys.EMOJI_PHONE,    "Telefon raqam yuborish","📱"),
        ]
    },
    "admin": {
        "title": "⚙️ Admin: Boshqaruv tugmalari (Reply)",
        "slots": [
            (SettingKeys.EMOJI_STATS,            "Statistika",          "📊"),
            (SettingKeys.EMOJI_USERS,            "Foydalanuvchilar",    "👥"),
            (SettingKeys.EMOJI_PRODUCTS,         "Mahsulotlar",         "🛍"),
            (SettingKeys.EMOJI_CATEGORIES,       "Kategoriyalar",       "📂"),
            (SettingKeys.EMOJI_BALANCE_REQUESTS, "Balans so'rovlari",   "💰"),
            (SettingKeys.EMOJI_ORDERS,           "Buyurtmalar",         "🛒"),
            (SettingKeys.EMOJI_BROADCAST,        "Xabar yuborish",      "📢"),
            (SettingKeys.EMOJI_SETTINGS,         "Sozlamalar",          "⚙️"),
            (SettingKeys.EMOJI_PREMIUM,          "Premium Emoji",       "✨"),
            (SettingKeys.EMOJI_BACK_HOME,        "Bosh menyuga",        "⬅️"),
        ]
    },
    "posts": {
        "title": "📝 Matn & Post emojilari",
        "slots": [
            (SettingKeys.EMOJI_SUCCESS,  "Muvaffaqiyat (✅)",    "✅"),
            (SettingKeys.EMOJI_ERROR,    "Xato (❌)",            "❌"),
            (SettingKeys.EMOJI_STAR,     "Yulduz (⭐)",          "⭐"),
            (SettingKeys.EMOJI_FIRE,     "Olov (🔥)",            "🔥"),
            (SettingKeys.EMOJI_CROWN,    "Toj (👑)",             "👑"),
            (SettingKeys.EMOJI_MONEY,    "Pul (💸)",             "💸"),
            (SettingKeys.EMOJI_LOCK,     "Qulf (🔒)",            "🔒"),
        ]
    }
}


# Tezkor qidirish uchun umumiy ro'yxat
ALL_SLOTS = {}
for cat_info in EMOJI_CATEGORIES.values():
    for key, label, fb in cat_info["slots"]:
        ALL_SLOTS[key] = (label, fb)


class EmojiStates(StatesGroup):
    waiting_for_id = State()


async def _save_emoji_to_db(session: AsyncSession, key: str, value: str | None) -> None:
    res = await session.execute(select(Setting).where(Setting.key == key))
    s = res.scalar_one_or_none()
    if value:
        if s:
            s.value = value
        else:
            session.add(Setting(key=key, value=value))
        set_emoji(key, value)
    else:
        if s:
            await session.delete(s)
        remove_emoji(key)
    await session.commit()


# ─────────────────────────────────────────────
# 1. Bosh kategoriya menyusi
# ─────────────────────────────────────────────
def _build_category_menu():
    active = get_all_emojis()
    builder = InlineKeyboardBuilder()

    lines = [
        "✨ <b>Telegram Premium Emoji boshqaruvi</b>\n",
        "Qaysi bo'limdagi tugma va matnlar emojisini o'zgartirmoqchisiz?\n"
    ]

    for cat_id, cat in EMOJI_CATEGORIES.items():
        count_active = sum(1 for k, _, _ in cat["slots"] if k in active)
        total = len(cat["slots"])
        builder.button(
            text=f"{cat['title']} ({count_active}/{total})",
            callback_data=f"emojicat_{cat_id}"
        )
        lines.append(f"• <b>{cat['title']}</b>: {count_active}/{total} ta sozlangan")

    builder.button(text="❌ Barcha emojilarni tozalash", callback_data="emoji_clear_all")
    builder.button(text="⬅️ Admin panelga qaytish", callback_data="emoji_back")
    builder.adjust(1)
    return "\n".join(lines), builder.as_markup()


@router.message(F.text.endswith("Premium Emoji"))
async def show_emoji_categories(message: Message, session: AsyncSession):
    from core.emoji import load_emojis
    await load_emojis(session)
    text, kb = _build_category_menu()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ─────────────────────────────────────────────
# 2. Tanlangan kategoriya ichidagi tugmalar
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("emojicat_"))
async def show_category_slots(callback: CallbackQuery):
    cat_id = callback.data.removeprefix("emojicat_")
    cat = EMOJI_CATEGORIES.get(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi!")
        return

    active = get_all_emojis()
    lines = [f"<b>{cat['title']}</b>\n", "O'zgartirmoqchi bo'lgan tugmangizni tanlang:\n"]
    builder = InlineKeyboardBuilder()

    for key, label, fallback in cat["slots"]:
        eid = active.get(key)
        if eid:
            icon = "🟢"
            status = f"<tg-emoji emoji-id=\"{eid}\">{fallback}</tg-emoji> (<code>{eid}</code>)"
        else:
            icon = "⚪"
            status = f"{fallback} (default)"

        builder.button(text=f"{icon} {fallback} {label}", callback_data=f"emoji_edit_{key}")
        lines.append(f"• <b>{label}</b>: {status}")

    builder.button(text="↩️ Kategoriyalar ro'yxatiga", callback_data="emoji_cats_back")
    builder.adjust(1)

    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ─────────────────────────────────────────────
# 3. Bitta emojini tahrirlash
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("emoji_edit_"))
async def ask_emoji_id(callback: CallbackQuery, state: FSMContext):
    key = callback.data.removeprefix("emoji_edit_")
    slot_info = ALL_SLOTS.get(key)
    if not slot_info:
        await callback.answer("Slot topilmadi!")
        return

    label, fallback = slot_info
    from core.emoji import _cache
    current_id = _cache.get(key)
    current_info = f"\n\n📌 <b>Joriy ID:</b> <code>{current_id}</code>" if current_id else "\n\n📌 <b>Hozircha:</b> Default oddiy emoji ishlatilmoqda."

    builder = InlineKeyboardBuilder()
    if current_id:
        builder.button(text="🗑 ID ni o'chirish (Default ga qaytarish)", callback_data=f"emoji_delete_{key}")
    builder.button(text="↩️ Orqaga", callback_data="emoji_cats_back")
    builder.adjust(1)

    text = (
        f"✨ <b>Tugma: {fallback} {label}</b>{current_info}\n\n"
        f"Telegram'dan nusxalangan <b>Custom Emoji ID</b> sini yuboring.\n\n"
        f"<blockquote>"
        f"💡 <b>Emoji ID olish usuli:</b>\n"
        f"Botingizga o'sha premium emojini yuboring yoki @get_emoji_id_robot botiga yuborib ID sini oling (masalan: <code>5373052667671093676</code>)."
        f"</blockquote>"
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.update_data(emoji_key=key, emoji_label=label, emoji_fallback=fallback)
    await state.set_state(EmojiStates.waiting_for_id)
    await callback.answer()


@router.message(EmojiStates.waiting_for_id, F.text)
async def process_emoji_id(message: Message, state: FSMContext, session: AsyncSession):
    raw = None
    # 1. To'g'ridan-to'g'ri custom emoji yuborilgan bo'lsa entity dan ID sini olamiz
    if message.entities:
        for ent in message.entities:
            if ent.type == "custom_emoji" and ent.custom_emoji_id:
                raw = str(ent.custom_emoji_id)
                break

    # 2. Matn ko'rinishida ID yuborilgan bo'lsa
    if not raw and message.text:
        raw = message.text.strip()

    if not raw or not raw.isdigit():
        await message.answer(
            "❌ <b>Noto'g'ri format!</b>\n\n"
            "Siz to'g'ridan-to'g'ri premium emojini o'zini yuborishingiz yoki uning ID sini (faqat raqam) yuborishingiz mumkin.\n"
            "Masalan: <code>5373052667671093676</code>",
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    key = data["emoji_key"]
    label = data["emoji_label"]
    fallback = data["emoji_fallback"]

    await _save_emoji_to_db(session, key, raw)
    await state.clear()

    preview = f'<tg-emoji emoji-id="{raw}">{fallback}</tg-emoji>'
    await message.answer(
        f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n\n"
        f"• Tugma: <b>{label}</b>\n"
        f"• Yangi ID: <code>{raw}</code>\n"
        f"• Ko'rinishi: {preview}\n\n"
        f"<i>Botdagi barcha tegishli keyboard va matnlarda ushbu emoji darhol yangilandi!</i>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# 4. O'chirish
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("emoji_delete_"))
async def delete_emoji(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    key = callback.data.removeprefix("emoji_delete_")
    label, _ = ALL_SLOTS.get(key, (key, ""))

    await _save_emoji_to_db(session, key, None)
    await state.clear()
    await callback.answer(f"🗑 {label} emojisi o'chirildi.", show_alert=True)

    text, kb = _build_category_menu()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "emoji_clear_all")
async def clear_all_emojis(callback: CallbackQuery, session: AsyncSession):
    from sqlalchemy import delete as sa_delete
    from db.models.setting import Setting
    from core.emoji import _cache

    await session.execute(sa_delete(Setting).where(Setting.key.like("emoji_%")))
    await session.commit()
    _cache.clear()

    await callback.answer("✅ Barcha premium emoji IDlari tozalandi.", show_alert=True)
    text, kb = _build_category_menu()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "emoji_cats_back")
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = _build_category_menu()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "emoji_back")
async def emoji_back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.admin.base import get_admin_keyboard
    await callback.message.delete()
    await callback.message.answer(
        "⚙ <b>Boshqaruv</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()
