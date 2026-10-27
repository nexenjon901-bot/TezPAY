"""
bot/handlers/admin/broadcast.py — Admin barchaga xabar / post yuborish
Telegram Premium emojilarni to'liq qo'llab-quvvatlaydi.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.filters.admin import IsAdmin
from bot.states.admin import BroadcastMessage
from db.models.user import User
from core.emoji import format_emojis, pe, btn_args

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📢 Xabar yuborish")
async def start_broadcast(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data="broadcast_cancel")

    guide = (
        f"📢 <b>Foydalanuvchilarga xabar (post) yuborish</b>\n\n"
        f"Yubormoqchi bo'lgan postingizni shu yerga yuboring (matn, rasm, video).\n\n"
        f"💡 <b>Premium Emojilardan foydalanish usullari:</b>\n"
        f"1. To'g'ridan-to'g'ri Telegram Premium emojilari bilan yozing.\n"
        f"2. Qulay kalit so'zlar: <code>{{shop}}</code>, <code>{{profile}}</code>, <code>{{balance}}</code>, <code>{{referral}}</code>, <code>{{useful}}</code>, <code>{{support}}</code>\n"
        f"3. Maxsus emoji ID bo'yicha: <code>{{emoji:5373052667671093676}}</code>\n\n"
        f"<i>Xabaringizni yuboring:</i>"
    )
    await message.answer(guide, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(BroadcastMessage.waiting_for_message)


@router.message(BroadcastMessage.waiting_for_message)
async def preview_broadcast(message: Message, state: FSMContext):
    # Matnni formatlaymiz (agar teglardan foydalanilgan bo'lsa)
    raw_text = message.html_text or message.caption or ""
    formatted_text = format_emojis(raw_text) if raw_text else None

    # State'ga saqlash
    await state.update_data(
        message_id=message.message_id,
        chat_id=message.chat.id,
        has_media=bool(message.photo or message.video or message.animation),
        formatted_text=formatted_text
    )

    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("confirm", "Barchaga yuborish"), callback_data="broadcast_confirm")
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data="broadcast_cancel")
    builder.adjust(2)

    await message.answer("👆 <b>Postingiz ko'rinishi (Preview) tayyorlandi.</b>\nBarchaga tarqatishni tasdiqlaysizmi?", reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(BroadcastMessage.waiting_for_confirm)


@router.callback_query(BroadcastMessage.waiting_for_confirm, F.data == "broadcast_confirm")
async def send_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    from_chat_id = data["chat_id"]
    from_msg_id = data["message_id"]
    formatted_text = data.get("formatted_text")

    users_res = await session.execute(select(User.telegram_id))
    user_ids = users_res.scalars().all()

    await callback.message.edit_text(f"⏳ Xabar {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")

    success = 0
    failed = 0
    bot = callback.bot

    for uid in user_ids:
        try:
            if formatted_text and data.get("has_media"):
                # Rasm yoki video bilan yuborilgan bo'lsa
                await bot.copy_message(chat_id=uid, from_chat_id=from_chat_id, message_id=from_msg_id, caption=formatted_text, parse_mode="HTML")
            elif formatted_text and not data.get("has_media"):
                # Oddiy matnli post
                await bot.send_message(chat_id=uid, text=formatted_text, parse_mode="HTML")
            else:
                # O'z holicha nusxalash
                await bot.copy_message(chat_id=uid, from_chat_id=from_chat_id, message_id=from_msg_id)
            success += 1
        except Exception:
            failed += 1

    await state.clear()
    await callback.message.answer(
        f"✅ <b>Xabar yuborish yakunlandi!</b>\n\n"
        f"• Muvaffaqiyatli: <b>{success}</b>\n"
        f"• Yetib bormadi (bloklaganlar): <b>{failed}</b>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Xabar yuborish bekor qilindi.")
    await callback.answer()
