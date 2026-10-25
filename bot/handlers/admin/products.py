from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from bot.filters.admin import IsAdmin
from db.models.product import Product
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from core.security import encrypt_text, decrypt_text

class ManageStock(StatesGroup):
    waiting_for_data = State()

class ProductStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_desc = State()
    waiting_for_image = State()

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _build_products_keyboard(products: list[Product]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi mahsulot", callback_data="adm_prod_add")
    for p in products:
        builder.button(text=f"{p.name} ({p.quantity} ta)", callback_data=f"adm_prod_view_{p.id}")
    builder.adjust(1)
    return builder


@router.message(F.text.endswith("Mahsulotlar"))
async def admin_products_list(message: Message, session: AsyncSession):
    res = await session.execute(select(Product))
    products = res.scalars().all()
    
    builder = _build_products_keyboard(products)
    txt = "📦 <b>Mahsulotlar</b>\n\nMahsulotni tanlang:" if products else "📦 <b>Mahsulotlar</b>\n\nHozircha mahsulotlar yo'q. Yangi mahsulot qo'shing:"
    await message.answer(txt, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "adm_prod_back")
async def admin_prod_back(callback: CallbackQuery, session: AsyncSession):
    res = await session.execute(select(Product))
    products = res.scalars().all()
    builder = _build_products_keyboard(products)
    txt = "📦 <b>Mahsulotlar</b>\n\nMahsulotni tanlang:" if products else "📦 <b>Mahsulotlar</b>\n\nHozircha mahsulotlar yo'q. Yangi mahsulot qo'shing:"
    try:
        await callback.message.edit_text(txt, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(txt, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm_prod_add")
async def add_prod_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    from db.models.product import Category
    res = await session.execute(select(Category).order_by(Category.order_index))
    categories = res.scalars().all()
    if not categories:
        await callback.answer("Avval kategoriya yarating!", show_alert=True)
        return
        
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=cat.name, callback_data=f"adm_prod_cat_{cat.id}")
    builder.button(text="↩️ Bekor qilish", callback_data="adm_prod_back")
    builder.adjust(1)
    
    await state.set_state(ProductStates.waiting_for_category)
    await callback.message.answer("Qaysi kategoriyaga qo'shasiz?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(ProductStates.waiting_for_category, F.data.startswith("adm_prod_cat_"))
async def add_prod_cat(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[3])
    await state.update_data(cat_id=cat_id)
    await state.set_state(ProductStates.waiting_for_name)
    await callback.message.answer("Mahsulot nomini kiriting:\nBekor qilish: /cancel")
    await callback.answer()


@router.message(ProductStates.waiting_for_name)
async def add_prod_name(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductStates.waiting_for_price)
    await message.answer("Narxini kiriting (UZS, faqat raqam):")


@router.message(ProductStates.waiting_for_price)
async def add_prod_price(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.")
        return
    try:
        raw = message.text.replace(" ", "").replace(",", "")
        price = float(raw)
        await state.update_data(price=price)
        await state.set_state(ProductStates.waiting_for_desc)
        await message.answer("Tavsifni kiriting:")
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting.")


@router.message(ProductStates.waiting_for_desc)
async def add_prod_desc(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.")
        return
        
    data = await state.get_data()
    new_prod = Product(
        category_id=data['cat_id'],
        name=data['name'],
        price_uzs=data['price'],
        description=message.text.strip(),
        is_active=True
    )
    session.add(new_prod)
    await session.commit()
    await session.refresh(new_prod)
    
    await state.update_data(prod_id=new_prod.id)
    await state.set_state(ProductStates.waiting_for_image)
    await message.answer(f"✅ Yaratildi: {new_prod.name}\nEndi rasm (photo) yuboring. O'tkazib yuborish: /skip")


@router.message(ProductStates.waiting_for_image, F.photo | F.text)
async def add_prod_image(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    prod_id = data.get("prod_id")
    prod = await session.get(Product, prod_id)
    
    if message.text == "/skip":
        await state.clear()
        await message.answer("Rasm o'tkazib yuborildi. Mahsulot saqlandi!")
        return
        
    if message.photo:
        file_id = message.photo[-1].file_id
        if prod:
            prod.image_file_id = file_id
            await session.commit()
        await state.clear()
        await message.answer("✅ Rasm va mahsulot muvaffaqiyatli saqlandi!")
    else:
        await message.answer("Rasm yuboring yoki /skip bosing.")


@router.callback_query(F.data.startswith("adm_prod_view_"))
async def admin_product_detail(callback: CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split("_")[3])
    p = await session.get(Product, pid)
    if not p:
        await callback.answer("Topilmadi", show_alert=True)
        return

    # Ombordagi haqiqiy mavjud va sotilgan tovarlarni hisoblash
    res_stock = await session.execute(
        text("SELECT status, count(*) FROM stock_items WHERE product_id = :pid GROUP BY status"),
        {"pid": pid}
    )
    stock_counts = dict(res_stock.fetchall())
    avail_count = stock_counts.get("AVAILABLE", 0)
    sold_count = stock_counts.get("SOLD", 0)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Omborga tovar qo'shish", callback_data=f"adm_addstock_{pid}")
    builder.button(text="📋 Mavjud tovarlarni ko'rish", callback_data=f"adm_viewstock_{pid}")
    builder.button(text="🗑 Omborni tozalash", callback_data=f"adm_clearstock_{pid}")
    builder.button(text="❌ Mahsulotni o'chirish", callback_data=f"adm_prod_del_{pid}")
    builder.button(text="↩️ Orqaga", callback_data="adm_prod_back")
    builder.adjust(1)
    
    price_str = f"{float(p.price_uzs):,.0f} so'm"
    txt = (
        f"🎮 <b>{p.name}</b>\n\n"
        f"<blockquote>"
        f"💰 <b>Narxi:</b> {price_str}\n"
        f"🟢 <b>Sotuvdagi ombor:</b> {avail_count} ta\n"
        f"🔴 <b>Sotilgan tovarlar:</b> {sold_count} ta\n"
        f"📄 <b>Tavsif:</b> {p.description or 'Mavjud emas'}"
        f"</blockquote>\n\n"
        f"<i>Ombor boshqaruvi uchun kerakli amalni tanlang:</i>"
    )
    try:
        await callback.message.edit_text(txt, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(txt, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_viewstock_"))
async def view_available_stock(callback: CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split("_")[2])
    res = await session.execute(
        text("SELECT id, data_encrypted, created_at FROM stock_items WHERE product_id = :pid AND status = 'AVAILABLE' ORDER BY id ASC LIMIT 20"),
        {"pid": pid}
    )
    rows = res.fetchall()
    
    if not rows:
        await callback.answer("Hozircha mavjud tovarlar yo'q!", show_alert=True)
        return
        
    lines = [f"📋 <b>Mavjud tovarlar ro'yxati (oxirgi {len(rows)} ta):</b>\n"]
    for idx, (sid, data_enc, cat_time) in enumerate(rows, 1):
        try:
            val = decrypt_text(data_enc)
        except Exception:
            val = "[Shifrlangan ma'lumot]"
        lines.append(f"{idx}. <code>{val}</code>")
        
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Mahsulotga qaytish", callback_data=f"adm_prod_view_{pid}")
    
    await callback.message.answer("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_clearstock_"))
async def clear_stock_confirm(callback: CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split("_")[2])
    
    await session.execute(
        text("DELETE FROM stock_items WHERE product_id = :pid AND status = 'AVAILABLE'"),
        {"pid": pid}
    )
    await session.execute(
        text("UPDATE products SET quantity = 0 WHERE id = :pid"),
        {"pid": pid}
    )
    await session.commit()
    await callback.answer("Ombordagi sotilmagan barcha tovarlar tozalandi!", show_alert=True)
    
    # Qayta ko'rsatish
    p = await session.get(Product, pid)
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Omborga tovar qo'shish", callback_data=f"adm_addstock_{pid}")
    builder.button(text="↩️ Mahsulotga qaytish", callback_data=f"adm_prod_view_{pid}")
    builder.adjust(1)
    await callback.message.edit_text(f"✅ <b>{p.name}</b> ombori muvaffaqiyatli tozalandi (0 ta).", reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_addstock_"))
async def add_stock_start(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[2])
    await state.update_data(product_id=pid)
    await state.set_state(ManageStock.waiting_for_data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Bekor qilish", callback_data=f"adm_prod_view_{pid}")
    
    await callback.message.answer(
        "📦 <b>Omborga tovar qo'shish bo'limi</b>\n\n"
        "Format namunalari:\n"
        "• Har bir qatorda bitta login/parol yoki promo/kod:\n"
        "<code>login1:parol1</code>\n"
        "<code>login2:parol2</code>\n\n"
        "📁 Yoki ichida qatorlab yozilgan <b>.txt fayl</b> yuklang.\n\n"
        "<i>Tizim avtomatik ravishda dublikatlarni tekshiradi va tozalaydi.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ManageStock.waiting_for_data)
async def process_add_stock(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.")
        return

    data = await state.get_data()
    pid = data.get("product_id")
    
    lines = []
    if message.document:
        if not message.document.file_name.endswith(".txt"):
            await message.answer("Faqat .txt fayl qabul qilinadi!")
            return
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        downloaded = await message.bot.download_file(file.file_path)
        content = downloaded.read().decode('utf-8')
        lines = [line.strip() for line in content.split('\n') if line.strip()]
    elif message.text:
        lines = [line.strip() for line in message.text.split('\n') if line.strip()]
    
    if not lines:
        await message.answer("Ma'lumot topilmadi!")
        return
        
    res = await session.execute(
        text("SELECT data_encrypted FROM stock_items WHERE product_id = :pid AND status = 'AVAILABLE'"),
        {"pid": pid}
    )
    existing_stock = res.fetchall()
    
    existing_texts = set()
    for row in existing_stock:
        try:
            existing_texts.add(decrypt_text(row[0]))
        except Exception:
            pass
            
    added = 0
    duplicates = 0
    
    for line in lines:
        if line in existing_texts:
            duplicates += 1
            continue
            
        enc = encrypt_text(line)
        await session.execute(
            text("INSERT INTO stock_items (product_id, data_encrypted, status, created_at) VALUES (:pid, :enc, 'AVAILABLE', NOW())"),
            {"pid": pid, "enc": enc}
        )
        existing_texts.add(line)
        added += 1
        
    if added > 0:
        await session.execute(
            text("UPDATE products SET quantity = quantity + :added WHERE id = :pid"),
            {"added": added, "pid": pid}
        )
        await session.commit()
        
    await message.answer(f"✅ <b>Bajarildi!</b>\n\nQo'shildi: {added} ta\nTakrorlanganlar: {duplicates} ta", parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("adm_prod_del_"))
async def delete_product(callback: CallbackQuery, session: AsyncSession):
    pid = int(callback.data.split("_")[3])
    # Bog'langan buyurtmalar va ombordagi tovarlarni tozalash
    await session.execute(text("UPDATE orders SET product_id = NULL WHERE product_id = :id"), {"id": pid})
    await session.execute(text("DELETE FROM stock_items WHERE product_id = :id"), {"id": pid})
    await session.execute(text("DELETE FROM products WHERE id = :id"), {"id": pid})
    await session.commit()
    await callback.answer("Mahsulot muvaffaqiyatli o'chirildi!", show_alert=True)
    await admin_prod_back(callback, session)
