from sqlalchemy import Column, String, Text, DateTime, func
from db.models.base import Base


class Setting(Base):
    """Bot sozlamalari — admin panel orqali boshqariladi"""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Default sozlamalar kalitlari
class SettingKeys:
    PAYMENT_CARD = "payment_card"           # Karta raqami
    PAYMENT_CARD_OWNER = "payment_card_owner"  # Karta egasi ismi
    PAYMENT_PHONE = "payment_phone"         # Karta/Uzcard ulanish telefoni
    SUPPORT_USERNAME = "support_username"   # Qo'llab-quvvatlash username
    CHANNEL_LINK = "channel_link"           # Kanal havolasi
    MIN_BALANCE = "min_balance"             # Minimal balans to'ldirish
    REFERRAL_PERCENT = "referral_percent"
    CASHBACK_PERCENT = "cashback_percent"
    MIN_WITHDRAWAL = "min_withdrawal"

    # ── 1. Asosiy menyu tugmalari (Inline) ──
    EMOJI_SHOP     = "emoji_shop"
    EMOJI_PROFILE  = "emoji_profile"
    EMOJI_BALANCE  = "emoji_balance"
    EMOJI_REFERRAL = "emoji_referral"
    EMOJI_USEFUL   = "emoji_useful"
    EMOJI_SUPPORT  = "emoji_support"
    EMOJI_ADMIN    = "emoji_admin"

    # ── 2. Admin panel tugmalari (Reply Keyboard) ──
    EMOJI_STATS            = "emoji_stats"
    EMOJI_USERS            = "emoji_users"
    EMOJI_PRODUCTS         = "emoji_products"
    EMOJI_CATEGORIES       = "emoji_categories"
    EMOJI_BALANCE_REQUESTS = "emoji_balance_requests"
    EMOJI_ORDERS           = "emoji_orders"
    EMOJI_BROADCAST        = "emoji_broadcast"
    EMOJI_SETTINGS         = "emoji_settings"
    EMOJI_PREMIUM          = "emoji_premium"
    EMOJI_BACK_HOME        = "emoji_back_home"

    # ── 3. Ichki tugmalar (Inline Keyboards) ──
    EMOJI_BACK     = "emoji_back"
    EMOJI_CART     = "emoji_cart"
    EMOJI_CONFIRM  = "emoji_confirm"
    EMOJI_CANCEL   = "emoji_cancel"
    EMOJI_HISTORY  = "emoji_history"
    EMOJI_GIFT     = "emoji_gift"
    EMOJI_PROMO    = "emoji_promo"
    EMOJI_LANG     = "emoji_lang"
    EMOJI_SHARE    = "emoji_share"
    EMOJI_CARD     = "emoji_card"
    EMOJI_CATEGORY = "emoji_category"
    EMOJI_PRODUCT  = "emoji_product"
    EMOJI_PHONE    = "emoji_phone"

    # ── 4. Post & Xabarlar uchun ──
    EMOJI_SUCCESS  = "emoji_success"
    EMOJI_ERROR    = "emoji_error"
    EMOJI_STAR     = "emoji_star"
    EMOJI_FIRE     = "emoji_fire"
    EMOJI_CROWN    = "emoji_crown"
    EMOJI_MONEY    = "emoji_money"
    EMOJI_LOCK     = "emoji_lock"
