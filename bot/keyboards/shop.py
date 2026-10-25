from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from typing import List
from db.models.product import Category, Product
from core.emoji import btn_args


def get_categories_keyboard(categories: List[Category], with_back: bool = True) -> InlineKeyboardMarkup:
    """Kategoriyalar ro'yxati uchun inline klaviatura"""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            **btn_args("category", cat.name),
            callback_data=f"shop_cat_{cat.id}"
        )
    if with_back:
        builder.button(**btn_args("back", "Orqaga"), callback_data="shop_back_main")
    builder.adjust(1)
    return builder.as_markup()


def get_products_keyboard(products: List[Product], category_id: int) -> InlineKeyboardMarkup:
    """Mahsulotlar ro'yxati uchun inline klaviatura (Screenshot 2 uslubida)"""
    builder = InlineKeyboardBuilder()
    for prod in products:
        status = f"{prod.quantity} dona" if prod.quantity > 0 else "0 dona"
        usd_val = float(prod.price_usd) if prod.price_usd else (float(prod.price_uzs) / 12700 if prod.price_uzs else 0)
        price_usd = f"${usd_val:.2f}"
        prod_text = f"{prod.name} — {status} — {price_usd}"
        builder.button(
            **btn_args("product", prod_text),
            callback_data=f"shop_prod_{prod.id}"
        )
    builder.button(**btn_args("back", "Orqaga"), callback_data="shop_back_cats")
    builder.adjust(1)
    return builder.as_markup()


def get_product_detail_keyboard(product: Product) -> InlineKeyboardMarkup:
    """Mahsulot batafsil uchun inline klaviatura"""
    builder = InlineKeyboardBuilder()
    if product.quantity > 0:
        builder.button(**btn_args("cart", "Sotib olish"), callback_data=f"shop_buy_{product.id}")
    else:
        builder.button(**btn_args("cancel", "Hozircha mavjud emas"), callback_data="shop_noop")
    builder.button(**btn_args("back", "Orqaga"), callback_data=f"shop_back_prod_{product.category_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_purchase_confirm_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Xarid tasdiqlash uchun klaviatura"""
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("confirm", "Tasdiqlash"), callback_data=f"shop_confirm_{product_id}")
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data=f"shop_back_prod_confirm_{product_id}")
    builder.adjust(1)
    return builder.as_markup()
