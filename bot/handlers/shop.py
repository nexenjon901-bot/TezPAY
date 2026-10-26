from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Callable
import os
from decimal import Decimal

from core.utils import format_money
from services.wallet import debit, TransactionType, InsufficientFunds
from sqlalchemy import text
from core.emoji import pe, btn_args

from db.models.product import Category, Product
from db.models.user import User
from db.models.order import Order, OrderStatus
from bot.keyboards.shop import (
    get_categories_keyboard,
    get_products_keyboard,
    get_product_detail_keyboard,
    get_purchase_confirm_keyboard,
)
from services.orders import generate_order_number

router = Router()

SHOP_BANNER = "bot/images/shop.png"
PRODUCT_BANNER = "bot/images/product_detail.png"


async def _get_banner(path: str):
    """Rasm fayli mavjud bo'lsa FSInputFile, aks holda None"""
    if os.path.exists(path):
        return FSInputFile(path)
    return None


# ───────────────────────────────────────────
# DO'KON — Asosiy sahifa (kategoriyalar)
# ───────────────────────────────────────────

async def show_shop(target, session: AsyncSession, db_user: User, _: Callable[[str], str] = None):
    cats_result = await session.execute(
        select(Category).where(Category.is_active ==
                               True).order_by(Category.order_index)
    )
    categories = cats_result.scalars().all()

    if not categories:
        txt = "😔 <b>Do'kon</b>\n\nHozircha mahsulotlar mavjud emas.\nTez orada qo'shiladi!"
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_caption(caption=txt, reply_markup=None)
            except Exception:
                await target.message.edit_text(txt)
        else:
            await target.answer(txt)
        return

    text = (
        f"{pe('shop')} <b>Do'kon</b>\n\n"
        "<blockquote>"
        "Mahsulotni tanlang — to'lov to'g'ridan-to'g'ri\n"
        "balansingizdan yechiladi va ma'lumotlar bir lahzada beriladi."
        "</blockquote>"
    )
    keyboard = get_categories_keyboard(categories, with_back=True)

    banner = await _get_banner(SHOP_BANNER)
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


@router.callback_query(F.data == "shop_back_cats")
async def back_to_categories(callback: CallbackQuery, session: AsyncSession):
    cats_result = await session.execute(
        select(Category).where(Category.is_active ==
                               True).order_by(Category.order_index)
    )
    categories = cats_result.scalars().all()
    keyboard = get_categories_keyboard(categories, with_back=True)

    text = (
        "🎮 <b>Do'kon</b>\n\n"
        "<blockquote>"
        "Mahsulotni tanlang — to'lov to'g'ridan-to'g'ri\n"
        "balansingizdan yechiladi va ma'lumotlar bir lahzada beriladi."
        "</blockquote>"
    )

    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()


# ───────────────────────────────────────────
# KATEGORIYA — Mahsulotlar ro'yxati
# ───────────────────────────────────────────

@router.callback_query(F.data.startswith("shop_cat_"))
async def show_category_products(callback: CallbackQuery, session: AsyncSession):
    cat_id = int(callback.data.split("_")[2])

    cat = await session.get(Category, cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return

    prods_result = await session.execute(
        select(Product)
        .where(Product.category_id == cat_id, Product.is_active == True)
        .order_by(Product.price_uzs)
    )
    products = prods_result.scalars().all()

    keyboard = get_products_keyboard(products, cat_id)
    text = (
        f"🎮 <b>{cat.name}</b>\n\n"
        f"<blockquote>"
        f"Mahsulotni tanlang — to'lov to'g'ridan-to'g'ri\n"
        f"balansingizdan yechiladi va ma'lumotlar bir lahzada beriladi."
        f"</blockquote>"
    )

    from aiogram.types import InputMediaPhoto
    media_file = cat.image_file_id if cat.image_file_id else FSInputFile(SHOP_BANNER)

    try:
        if media_file:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=media_file, caption=text, parse_mode="HTML"),
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        except Exception:
            pass
    await callback.answer()


# ───────────────────────────────────────────
# MAHSULOT — Batafsil ma'lumot
# ───────────────────────────────────────────

@router.callback_query(F.data.startswith("shop_prod_"))
async def show_product_detail(callback: CallbackQuery, session: AsyncSession):
    prod_id = int(callback.data.split("_")[2])
    prod = await session.get(Product, prod_id)

    if not prod:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    usd_val = float(prod.price_usd) if prod.price_usd else (float(prod.price_uzs) / 12700 if prod.price_uzs else 0)
    price_usd = f"${usd_val:.2f}"
    status_text = f"{prod.quantity} dona" if prod.quantity > 0 else "0 dona"
    description = prod.description or "Avtomatik yetkazib berish."

    # Screenshot 3 uslubidagi blockquote format
    text = (
        f"📦 <b>{prod.name}</b>\n\n"
        f"<blockquote>"
        f"💰 Narxi: {float(prod.price_uzs):,.0f} so'm ({price_usd})\n"
        f"📦 Mavjud: {status_text}\n\n"
        f"📄 Tavsif: {description}"
        f"</blockquote>\n\n"
        f"<i>Xarid qilish uchun quyidagi tugmani bosing:</i>"
    )

    keyboard = get_product_detail_keyboard(prod)

    from aiogram.types import InputMediaPhoto
    
    # Try product image, fallback to category image, fallback to PRODUCT_BANNER
    cat = await session.get(Category, prod.category_id)
    media_file = prod.image_file_id
    if not media_file and cat:
        media_file = cat.image_file_id
    if not media_file:
        media_file = FSInputFile(PRODUCT_BANNER)

    try:
        if media_file:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=media_file, caption=text, parse_mode="HTML"),
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("shop_back_prod_"))
async def back_to_product_list(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split("_")
    # shop_back_prod_{cat_id} va shop_back_prod_confirm_{prod_id} ni ajratamiz
    if parts[3] == "confirm":
        prod_id = int(parts[4])
        prod = await session.get(Product, prod_id)
        cat_id = prod.category_id if prod else 1
    else:
        cat_id = int(parts[3])

    prods_result = await session.execute(
        select(Product)
        .where(Product.category_id == cat_id, Product.is_active == True)
        .order_by(Product.price_uzs)
    )
    products = prods_result.scalars().all()
    cat = await session.get(Category, cat_id)

    keyboard = get_products_keyboard(products, cat_id)
    text = f"🛍 <b>Do'kon</b>\n\n🎮 <b>{cat.name if cat else 'Kategoriya'}</b>\n\nQuyidagi mahsulotlardan birini tanlang:"

    from aiogram.types import InputMediaPhoto
    media_file = cat.image_file_id if (cat and cat.image_file_id) else FSInputFile(SHOP_BANNER)

    try:
        if media_file:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=media_file, caption=text, parse_mode="HTML"),
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.edit_text(text=text, reply_markup=keyboard)
        except Exception:
            pass
    await callback.answer()


# ───────────────────────────────────────────
# XARID — Tasdiqlash va bajarish
# ───────────────────────────────────────────

@router.callback_query(F.data.startswith("shop_buy_"))
async def start_purchase(callback: CallbackQuery, session: AsyncSession, db_user: User):
    prod_id = int(callback.data.split("_")[2])
    prod = await session.get(Product, prod_id)

    if not prod or not prod.is_active:
        await callback.answer("❌ Mahsulot mavjud emas!", show_alert=True)
        return

    if prod.quantity <= 0:
        await callback.answer("❌ Afsuski, hozircha stokda yo'q!", show_alert=True)
        return

    balance = db_user.balance or Decimal('0')
    price = prod.price_uzs
    price_usd = f"${prod.price_usd:.2f}" if prod.price_usd else ""

    if balance < price:
        needed = price - balance
        await callback.answer(
            f"❌ Balansingiz yetarli emas!\n"
            f"Balans: {format_money(balance)}\n"
            f"Kerak: {format_money(price)}\n"
            f"Yetishmaydi: {format_money(needed)}\n\n"
            f"Balansni to'ldiring!",
            show_alert=True
        )
        return

    text = (
        f"🛍 <b>Xarid tasdiqlash</b>\n\n"
        f"🎮 <b>{prod.name}</b>\n"
        f"💰 Narxi: <b>{format_money(price)} ({price_usd})</b>\n"
        f"💳 Sizning balansingiz: <b>{format_money(balance)}</b>\n\n"
        f"Xaridni tasdiqlaysizmi?"
    )

    keyboard = get_purchase_confirm_keyboard(prod_id)
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("shop_confirm_"))
async def confirm_purchase(callback: CallbackQuery, session: AsyncSession, db_user: User):
    prod_id = int(callback.data.split("_")[2])
    
    # Order number generation
    order_num = await generate_order_number(session)

    # 1. SKIP LOCKED bilan bo'sh stock_item ni qidiramiz va bloklaymiz
    res_stock = await session.execute(
        text("""
            SELECT id, data_encrypted 
            FROM stock_items 
            WHERE product_id = :pid AND status = 'AVAILABLE' 
            FOR UPDATE SKIP LOCKED 
            LIMIT 1
        """),
        {"pid": prod_id}
    )
    stock_row = res_stock.fetchone()
    if not stock_row:
        await callback.answer("❌ Kechirasiz, mahsulot aynan hozir tugab qoldi!", show_alert=True)
        return
    
    stock_id, data_encrypted = stock_row
    
    # 2. Mahsulot nomi va narxini olish
    res_prod = await session.execute(
        text("SELECT name, price_uzs FROM products WHERE id = :id"),
        {"id": prod_id}
    )
    prod_name, price = res_prod.fetchone()
    
    # 3. Atomik ravishda pulni yechamiz
    try:
        await debit(session, db_user.id, price, TransactionType.PURCHASE, ref_type="order", ref_id=order_num)
    except InsufficientFunds:
        await session.rollback()
        await callback.answer("❌ Balansingiz yetarli emas!", show_alert=True)
        return
    except Exception as e:
        await session.rollback()
        await callback.answer("❌ Tizimda xatolik yuz berdi!", show_alert=True)
        return

    # 4. Order yaratamiz
    order = Order(
        order_number=order_num,
        user_id=db_user.id,
        product_id=prod_id,
        product_quantity=1,
        price=price,
        status=OrderStatus.COMPLETED,
    )
    session.add(order)
    await session.flush()
    
    # 5. StockItem ni sotilgan deb belgilash
    await session.execute(
        text("""
            UPDATE stock_items 
            SET status = 'SOLD', order_id = :oid, sold_to_user_id = :uid, sold_at = NOW() 
            WHERE id = :sid
        """),
        {"oid": order.id, "uid": db_user.id, "sid": stock_id}
    )
    
    # 6. Product qoldig'ini yangilash (denormalizatsiya)
    res_qty = await session.execute(
        text("UPDATE products SET quantity = quantity - 1 WHERE id = :pid RETURNING quantity"),
        {"pid": prod_id}
    )
    remaining_qty = res_qty.scalar() or 0

    # 7. Cashback (Dynamic from settings)
    from decimal import Decimal
    from db.models.setting import Setting, SettingKeys
    
    async def get_setting_float(key, default):
        res = await session.execute(select(Setting).where(Setting.key == key))
        s = res.scalar_one_or_none()
        try:
            return float(s.value) if s else default
        except Exception:
            return default
            
    cb_pct = await get_setting_float(SettingKeys.CASHBACK_PERCENT, 1.0)
    ref_pct = await get_setting_float(SettingKeys.REFERRAL_PERCENT, 2.0)
    
    buyer_cb = Decimal(str(price)) * Decimal(str(cb_pct / 100))
    if buyer_cb > 0:
        await session.execute(
            text("UPDATE users SET ref_balance = ref_balance + :cb WHERE id = :uid"),
            {"cb": buyer_cb, "uid": db_user.id}
        )
        
    if db_user.referred_by:
        referrer_cb = Decimal(str(price)) * Decimal(str(ref_pct / 100))
        if referrer_cb > 0:
            await session.execute(
                text("UPDATE users SET ref_balance = ref_balance + :cb WHERE referral_code = :ref"),
                {"cb": referrer_cb, "ref": db_user.referred_by}
            )

    await session.commit()
    await session.refresh(db_user)

    # 8. Shifrdan yechish
    from core.security import decrypt_text
    try:
        decrypted_data = decrypt_text(data_encrypted)
    except Exception:
        decrypted_data = "Ma'lumotni o'qishda xatolik. Admin bilan bog'laning."
        # Optionally update order status to DELIVERY_FAILED here
        
    text_msg = (
        f"{pe('success')} <b>Xarid muvaffaqiyatli amalga oshirildi!</b>\n\n"
        f"<blockquote>"
        f"🧾 Buyurtma: <code>#{order_num}</code>\n"
        f"🎮 Mahsulot: <b>{prod_name}</b>\n"
        f"💰 Narxi: <b>{format_money(price)}</b>\n"
        f"💳 Qolgan balans: <b>{format_money(db_user.balance)}</b>\n\n"
        f"🔑 <b>Hisob ma'lumotlari:</b>\n"
        f"<code>{decrypted_data}</code>"
        f"</blockquote>\n\n"
        f"<i>Xaridingiz uchun rahmat! Barcha xaridlaringiz profil bo'limida saqlanadi.</i>"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from core.emoji import btn_args
    done_builder = InlineKeyboardBuilder()
    done_builder.button(**btn_args("back", "Bosh menyu"), callback_data="shop_back_main")

    try:
        await callback.message.edit_caption(caption=text_msg, reply_markup=done_builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text=text_msg, reply_markup=done_builder.as_markup())
        except Exception:
            # Telegram yetkazish xatosi (foydalanuvchi bloklagan yoki chat topilmadi)
            await session.execute(text("UPDATE orders SET status = 'DELIVERY_FAILED' WHERE id = :oid"), {"oid": order.id})
            await session.commit()
            
            from core.config import config as _config
            try:
                await callback.bot.send_message(_config.ADMIN_ID, f"⚠️ <b>YETKAZISH XATOSI</b>\nBuyurtma: <code>{order_num}</code>\nXaridorga ma'lumot yetib bormadi (bloklagan bo'lishi mumkin).")
            except Exception:
                pass
                
    try:
        await callback.answer("✅ Ma'lumot yetkazildi!")
    except Exception:
        pass

    # Admin ga xabar yuborish
    from aiogram import Bot
    from core.config import config as _config
    bot: Bot = callback.bot
    buyer = f"@{db_user.username}" if db_user.username else f"ID: {db_user.telegram_id}"
    admin_text = (
        f"🛒 <b>YANGI XARID</b>\n\n"
        f"🧾 Buyurtma: <code>{order_num}</code>\n"
        f"🎮 Mahsulot: <b>{prod_name}</b>\n"
        f"👤 Xaridor: {buyer}\n"
        f"💰 Summa: {format_money(price)}\n\n"
        f"📦 Qoldiq: <b>{remaining_qty} dona</b>"
    )
    try:
        await bot.send_message(_config.ADMIN_ID, admin_text)
    except Exception:
        pass

    # ⚠️ Kam qolgan stock ogohlantirishi (agar <= 3 bo'lsa)
    if remaining_qty <= 3:
        try:
            warning_text = (
                f"⚠️ <b>DIQQAT: STOKDA KAM QOLDI!</b>\n\n"
                f"🎮 Mahsulot: <b>{prod_name}</b>\n"
                f"📦 Qolgan zaxira: <b>{remaining_qty} dona</b>\n\n"
                f"<i>Iltimos, zaxirani to'ldiring yoki mahsulot holatini tekshiring.</i>"
            )
            await bot.send_message(_config.ADMIN_ID, warning_text)
        except Exception:
            pass

    # ───────────────────────────────────────────
    # KANALGA AVTOMATIK XARID POSTINI CHIQARISH
    # ───────────────────────────────────────────
    try:
        # Xaridor ismini maskalash: "Ali***" yoki "@us***"
        if db_user.username:
            uname = db_user.username
            masked = f"@{uname[:2]}{'*' * min(len(uname) - 2, 5)}" if len(uname) > 2 else f"@{uname}"
        elif db_user.first_name:
            fname = db_user.first_name
            masked = f"{fname[:2]}{'*' * min(len(fname) - 2, 5)}" if len(fname) > 2 else fname
        else:
            masked = "Foydalanuvchi"

        # USD narxni hisoblash
        usd_val = float(price) / 12700
        price_usd_str = f"${usd_val:.2f}"

        channel_text = (
            f"{pe('fire')} <b>YANGI XARID!</b>\n\n"
            f"<blockquote>"
            f"{pe('shop')} Mahsulot: <b>{prod_name}</b>\n"
            f"{pe('money')} Narxi: <b>{format_money(price)}</b> ({price_usd_str})\n"
            f"👤 Xaridor: <b>{masked}</b>\n"
            f"🧾 Buyurtma: <code>#{order_num}</code>"
            f"</blockquote>\n\n"
            f"{pe('star')} <i>Siz ham xarid qiling — qulay va tezkor!</i>"
        )

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        ch_builder = InlineKeyboardBuilder()
        ch_builder.button(
            **btn_args("shop", "Do'konga o'tish"),
            url=f"https://t.me/{_config.BOT_USERNAME}?start=shop"
        )
        ch_builder.adjust(1)

        await bot.send_message(
            chat_id=_config.ORDERS_CHANNEL_ID,
            text=channel_text,
            reply_markup=ch_builder.as_markup()
        )
    except Exception as ch_err:
        # Kanal xatosi xarid jarayoniga ta'sir qilmasligi kerak
        from core.logger import logger
        logger.warning(f"Kanalga post yuborishda xato: {ch_err}")


@router.callback_query(F.data == "shop_noop")
async def shop_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "shop_back_main")
async def back_to_main(callback: CallbackQuery):
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
