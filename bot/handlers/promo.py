from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.states.promo import PromoState
from db.models.user import User
from services.promo import activate_promo_code, PromoError
from core.emoji import pe, btn_args
from core.utils import format_money

router = Router()


@router.callback_query(F.data == "enter_promo_code")
async def start_promo_input(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromoState.waiting_for_code)

    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data="promo_cancel")
    builder.adjust(1)

    text = (
        f"{pe('gift')} <b>Promo-kodni faollashtirish</b>\n\n"
        "Rasmiy kanalimizda yoki aksiyalarda berilgan maxsus promo-kodni kiriting:\n\n"
        "<i>Masalan: <code>YANGIYIL2026</code></i>"
    )

    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup())
    except Exception:
        try:
            await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text=text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(Command("promo"))
@router.message(Command("voucher"))
async def cmd_promo(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not db_user:
        await message.answer("❌ Avval ro'yxatdan o'ting: /start")
        return

    # Foydalanuvchi /promo KOD ko'rinishida yozgan bo'lsa
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        code = args[1].strip()
        await _process_code_string(message, code, session, db_user)
        return

    await state.set_state(PromoState.waiting_for_code)
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("cancel", "Bekor qilish"), callback_data="promo_cancel")
    builder.adjust(1)

    text = (
        f"{pe('gift')} <b>Promo-kodni faollashtirish</b>\n\n"
        "Promo-kodni kiriting:\n\n"
        "<i>Masalan: <code>YANGIYIL2026</code></i>"
    )
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "promo_cancel")
async def cancel_promo(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Bekor qilindi.")
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.message(PromoState.waiting_for_code, F.text)
async def process_promo_input(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not db_user:
        await message.answer("❌ Avval ro'yxatdan o'ting: /start")
        await state.clear()
        return

    code = message.text.strip()
    await state.clear()
    await _process_code_string(message, code, session, db_user)


async def _process_code_string(message: Message, code: str, session: AsyncSession, db_user: User):
    try:
        reward, new_balance = await activate_promo_code(session, db_user.id, code)

        builder = InlineKeyboardBuilder()
        builder.button(**btn_args("shop", "Do'konga o'tish"), callback_data="menu_shop")
        builder.button(**btn_args("profile", "Profilni ko'rish"), callback_data="menu_profile")
        builder.adjust(1)

        text = (
            f"🎉 <b>Promo-kod faollashtirildi!</b>\n\n"
            f"<blockquote>"
            f"🎁 Mukofot: <b>+{format_money(reward)}</b>\n"
            f"💰 Yangi balans: <b>{format_money(new_balance)}</b>\n\n"
            f"Mablag' balansingizga qo'shildi. Do'kondan xarid qilishingiz mumkin."
            f"</blockquote>"
        )
        await message.answer(text, reply_markup=builder.as_markup())

    except PromoError as e:
        builder = InlineKeyboardBuilder()
        builder.button(**btn_args("gift", "Qayta urinish"), callback_data="enter_promo_code")
        builder.button(**btn_args("back", "Bosh menyu"), callback_data="menu_back_main")
        builder.adjust(1)

        await message.answer(f"{str(e)}", reply_markup=builder.as_markup())
    except Exception:
        builder = InlineKeyboardBuilder()
        builder.button(**btn_args("back", "Bosh menyu"), callback_data="menu_back_main")
        await message.answer("❌ Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.", reply_markup=builder.as_markup())
