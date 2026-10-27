"""
core/emoji.py — Telegram Premium Emoji boshqaruv moduli

Funksiyalar:
  - pe(key): xabar matniga <tg-emoji> tegi yoki fallback emoji
  - peb(key): oddiy unicode emoji (fallback)
  - pe_id(key): faqat custom emoji ID yoki None
  - btn_args(key, text): InlineKeyboardButton argumentlari (icon_custom_emoji_id bilan)
  - reply_btn(key, text): KeyboardButton (icon_custom_emoji_id bilan)
  - format_emojis(text): matndagi barcha {shop}, {balance}, {emoji:ID} larni <tg-emoji> ga aylantirish
"""

from __future__ import annotations
import re
from typing import Optional
from aiogram.types import KeyboardButton


# ─────────────────────────────────────────────
# Fallback (oddiy) emojilar xaritasi
# ─────────────────────────────────────────────
_FALLBACK: dict[str, str] = {
    # 1. Asosiy menyu
    "emoji_shop":             "🛍️",
    "emoji_profile":          "👤",
    "emoji_balance":          "💰",
    "emoji_referral":         "🤝",
    "emoji_useful":           "📄",
    "emoji_support":          "🧑‍💻",
    "emoji_admin":            "⚙️",

    # 2. Admin panel
    "emoji_stats":            "📊",
    "emoji_users":            "👥",
    "emoji_products":         "🛍",
    "emoji_categories":       "📂",
    "emoji_balance_requests": "💰",
    "emoji_orders":           "🛒",
    "emoji_broadcast":        "📢",
    "emoji_settings":         "⚙️",
    "emoji_promo_admin":      "🎟",
    "emoji_premium":          "✨",
    "emoji_back_home":        "⬅️",

    # 3. Ichki tugmalar
    "emoji_back":             "↩️",
    "emoji_cart":             "🛒",
    "emoji_confirm":          "✅",
    "emoji_cancel":           "❌",
    "emoji_history":          "📋",
    "emoji_gift":             "🎁",
    "emoji_promo":            "🎟",
    "emoji_lang":             "🌐",
    "emoji_share":            "📲",
    "emoji_card":             "💳",
    "emoji_category":         "🎮",
    "emoji_product":          "🎮",
    "emoji_phone":            "📱",

    # 4. Post & Xabarlar
    "emoji_success":          "✅",
    "emoji_error":            "❌",
    "emoji_star":             "⭐",
    "emoji_fire":             "🔥",
    "emoji_crown":            "👑",
    "emoji_money":            "💸",
    "emoji_lock":             "🔒",
    "emoji_welcome":          "👋",
    "emoji_card_post":        "💳",
    "emoji_warning":          "⚠️",
    "emoji_gift_post":        "🎁",
    "emoji_link":             "🔗",
    "emoji_time":             "⏰",
    "emoji_bell":             "🔔",
    "emoji_search":           "🔍",
    "emoji_delete":           "🗑️",
    "emoji_toggle":           "🔄",
}

# Xotiradagi kesh: { slug: emoji_id }
_cache: dict[str, str] = {}


def _build_tag(emoji_id: str, fallback: str) -> str:
    """<tg-emoji emoji-id="...">fallback</tg-emoji> HTML tegi yaratish."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def pe(key: str) -> str:
    """Xabar matni uchun <tg-emoji> tegi yoki oddiy fallback emoji."""
    full_key = key if key.startswith("emoji_") else f"emoji_{key}"
    fallback = _FALLBACK.get(full_key, "⭐")
    emoji_id = _cache.get(full_key)
    if emoji_id:
        return _build_tag(emoji_id, fallback)
    return fallback


def peb(key: str) -> str:
    """Faqat oddiy unicode fallback emoji qaytaradi."""
    full_key = key if key.startswith("emoji_") else f"emoji_{key}"
    return _FALLBACK.get(full_key, "⭐")


def pe_id(key: str) -> Optional[str]:
    """Faqat emoji ID sini qaytaradi (yoki None)."""
    full_key = key if key.startswith("emoji_") else f"emoji_{key}"
    return _cache.get(full_key)


def btn_args(key: str, text: str) -> dict:
    """
    InlineKeyboardButton uchun argumentlar to'plami.
    Agar emoji ID mavjud bo'lsa icon_custom_emoji_id ishlatiladi.
    Aks holda text oldiga oddiy unicode fallback emoji qo'yiladi.
    """
    eid = pe_id(key)
    if eid:
        return {"text": text, "icon_custom_emoji_id": eid}
    fallback = _FALLBACK.get(key if key.startswith("emoji_") else f"emoji_{key}", "")
    return {"text": f"{fallback} {text}".strip()}


def reply_btn(key: str, text: str, **kwargs) -> KeyboardButton:
    """
    Reply KeyboardButton yaratish.
    Agar emoji ID mavjud bo'lsa icon_custom_emoji_id ishlatiladi.
    Aks holda text oldiga oddiy unicode fallback emoji qo'yiladi.
    """
    eid = pe_id(key)
    if eid:
        return KeyboardButton(text=text, icon_custom_emoji_id=eid, **kwargs)
    fallback = _FALLBACK.get(key if key.startswith("emoji_") else f"emoji_{key}", "")
    return KeyboardButton(text=f"{fallback} {text}".strip(), **kwargs)


def set_emoji(key: str, emoji_id: str) -> None:
    """Keshga yangi emoji ID yozish."""
    full_key = key if key.startswith("emoji_") else f"emoji_{key}"
    _cache[full_key] = emoji_id.strip()


def remove_emoji(key: str) -> None:
    """Keshdan emoji ID o'chirish."""
    full_key = key if key.startswith("emoji_") else f"emoji_{key}"
    _cache.pop(full_key, None)


def get_all_emojis() -> dict[str, str]:
    """Barcha sozlangan emojilarni qaytaradi { full_key: emoji_id }."""
    return dict(_cache)


async def load_emojis(session) -> None:
    """Barcha premium emoji IDlarini DB dan yuklash."""
    from sqlalchemy import select
    from db.models.setting import Setting

    result = await session.execute(
        select(Setting).where(Setting.key.like("emoji_%"))
    )
    rows = result.scalars().all()
    _cache.clear()
    for row in rows:
        if row.value:
            _cache[row.key] = row.value


def format_emojis(text: str) -> str:
    """
    Matn ichidagi {shop}, {balance}, {emoji:ID} kabi teglarni <tg-emoji> ga aylantiradi.
    """
    if not text:
        return text

    # 1. To'g'ridan-to'g'ri ID format: {emoji:1234567890} yoki [emoji:1234567890]
    def _replace_direct_id(match):
        emoji_id = match.group(1)
        return _build_tag(emoji_id, "⭐")

    text = re.sub(r"[\{\[]emoji:(\d+)[\}\]]", _replace_direct_id, text)

    # 2. Kalit so'zlar: {shop}, :shop:
    for full_key, emoji_id in _cache.items():
        short_name = full_key.removeprefix("emoji_")
        tag = _build_tag(emoji_id, _FALLBACK.get(full_key, "⭐"))
        text = text.replace(f"{{{short_name}}}", tag)
        text = text.replace(f":{short_name}:", tag)

    # Agar keshda ID yo'q bo'lsa, fallback emojiga aylantiramiz
    for full_key, fallback in _FALLBACK.items():
        short_name = full_key.removeprefix("emoji_")
        text = text.replace(f"{{{short_name}}}", fallback)
        text = text.replace(f":{short_name}:", fallback)

    return text
