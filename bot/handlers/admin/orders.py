from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models.order import Order, OrderStatus
from db.models.account import Account, AccountStatus
from db.models.user import User
from bot.filters.admin import IsAdmin
from core.config import config

router = Router()
router.callback_query.filter(IsAdmin())


@router.message(F.text.endswith("Buyurtmalar"))
async def list_pending_orders(message: Message, session: AsyncSession):
    # Fetch orders in PAYMENT_REVIEW state
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.payment), selectinload(Order.user), selectinload(Order.account))
        .where(Order.status == OrderStatus.PAYMENT_REVIEW)
        .order_by(Order.created_at.asc())
        .limit(1)  # We process one by one for simplicity in MVP
    )
    order = result.scalar_one_or_none()

    if not order:
        await message.answer("Yangi buyurtmalar yo'q.")
        return

    text = f"🛍 <b>Order:</b> {order.order_number}\n"
    text += f"👤 <b>Buyer:</b> {order.user.first_name} (@{order.user.username})\n"
    text += f"🎮 <b>Account ID:</b> {order.account_id}\n"
    text += f"💰 <b>Amount:</b> {order.price:,.0f} UZS\n"
    text += f"💳 <b>Method:</b> {order.payment.method}\n\n"
    text += "Verify the payment receipt below."

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=f"adm_approve_{order.id}")
    builder.button(text="❌ Reject", callback_data=f"adm_reject_{order.id}")
    # builder.button(text="➡️ Next", callback_data="admin_orders") # simplified pagination
    builder.adjust(2)

    if order.payment.receipt_file_id:
        await message.answer_photo(
            photo=order.payment.receipt_file_id,
            caption=text,
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("adm_approve_"))
async def approve_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    order_id = int(callback.data.split("_")[2])

    # Fetch order and related credential
    # Need to load the credential explicitly since it's related to Account
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.account), selectinload(Order.user))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order or order.status != OrderStatus.PAYMENT_REVIEW:
        await callback.answer("Order not found or already processed.", show_alert=True)
        return

    # Update status
    order.status = OrderStatus.APPROVED
    order.account.status = AccountStatus.SOLD
    await session.commit()

    # Inform the user that payment is approved and admin will contact them
    user_msg = (
        f"🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
        f"🧾 <b>Buyurtma:</b> {order.order_number}\n\n"
        f"⏳ Admin tez orada sizga akkaunt login va parolini shaxsiy xabarda yuboradi."
    )

    try:
        await bot.send_message(order.user.telegram_id, user_msg)
    except Exception as e:
        pass

    # Also notify the public Orders Channel
    channel_msg = (
        f"🛒 <b>YANGI XARID AMALGA OSHIRILDI</b>\n\n"
        f"🧾 <b>Buyurtma:</b> {order.order_number}\n"
        f"🎮 <b>Akkaunt:</b> #{order.account.id}\n"
        f"💰 <b>Narxi:</b> {order.price:,.0f} {order.account.currency}\n"
        f"✅ <b>Holati:</b> Sotildi"
    )

    try:
        if config.ORDERS_CHANNEL_ID:
            await bot.send_message(config.ORDERS_CHANNEL_ID, channel_msg)
    except Exception:
        pass

    # Complete order
    order.status = OrderStatus.COMPLETED
    await session.commit()

    buyer_info = f"@{order.user.username}" if order.user.username else f"ID: {order.user.telegram_id}"
    admin_success_msg = (
        f"✅ Buyurtma {order.order_number} TASDIQLANDI.\n\n"
        f"👤 Xaridor: {buyer_info}\n"
        f"❗️ <b>Iltimos, xaridorning shaxsiy xabariga o'tib akkaunt login va parolini yuboring.</b>"
    )

    await callback.message.edit_caption(caption=admin_success_msg)
