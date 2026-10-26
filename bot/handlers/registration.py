import secrets
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.states.registration import Registration
from db.models.user import User
from typing import Callable
from core.config import config
from core.emoji import pe, peb, btn_args, reply_btn, format_emojis

router = Router()

MAIN_MENU_BANNER = "bot/images/menu.png"


def get_main_menu_keyboard(_: Callable[[str], str] = None, is_admin: bool = False):
    """Asosiy menyu - inline keyboard (Screenshot 1 uslubida)"""
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("shop", "Do'kon"), callback_data="menu_shop")
    builder.button(**btn_args("profile", "Profil"), callback_data="menu_profile")
    builder.button(**btn_args("balance", "Balans to'ldirish"), callback_data="menu_balance")
    builder.button(**btn_args("useful", "Foydali"), callback_data="menu_useful")
    builder.button(**btn_args("referral", "Referal tizimi"), callback_data="menu_referral")
    builder.button(**btn_args("support", "Qo'llab-quvvatlash"), url=config.SUPPORT_URL)
    if is_admin:
        builder.button(**btn_args("admin", "Admin panel"), callback_data="menu_admin")
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()


def _generate_referral_code(telegram_id: int) -> str:
    """Unikal referal kod yaratish"""
    return f"REF{telegram_id % 100000:05d}{secrets.token_hex(2).upper()}"


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, session: AsyncSession, db_user: User, _: Callable[[str], str]):
    is_admin = message.from_user.id in config.all_admin_ids

    if db_user:
        # Referal kodi yo'q bo'lsa — yaratib qo'yamiz
        if not db_user.referral_code:
            db_user.referral_code = _generate_referral_code(
                message.from_user.id)
            session.add(db_user)
            await session.commit()

        first_name = db_user.first_name or "Foydalanuvchi"
        text = (
            f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\n"
            f"<blockquote>"
            f"Do'konimizga xush kelibsiz! O'zingizga ma'qul bo'limni tanlang va qulay xarid qiling."
            f"</blockquote>"
        )

        if os.path.exists(MAIN_MENU_BANNER):
            await message.answer_photo(photo=FSInputFile(MAIN_MENU_BANNER), caption=text, reply_markup=get_main_menu_keyboard(_, is_admin=is_admin))
        else:
            await message.answer(text, reply_markup=get_main_menu_keyboard(_, is_admin=is_admin))
        return

    # Ro'yxatdan o'tmagan — til tanlash
    builder = InlineKeyboardBuilder()
    builder.button(**btn_args("lang", "O'zbek tili"), callback_data="lang_uz")
    builder.button(**btn_args("lang", "Русский"),    callback_data="lang_ru")
    builder.button(**btn_args("lang", "English"),    callback_data="lang_en")
    builder.adjust(1)

    # Agar /start ref_XXX bilan kelsa — referal kodi saqlash
    args = message.text.split() if message.text else []
    ref_code = args[1] if len(args) > 1 else None
    if ref_code:
        await state.update_data(ref_code=ref_code)

    welcome_text = (
        "👋 <b>Xush kelibsiz! / Добро пожаловать! / Welcome!</b>\n\n"
        "🛍 <b>ENTELLI STORE</b> — O'zbekistonning eng ishonchli PUBG akkauntlari savdo markazi.\n\n"
        "🌐 Iltimos, o'zingizga qulay tilni tanlang:\n"
        "🌐 Пожалуйста, выберите удобный для вас язык:\n"
        "🌐 Please select your preferred language:"
    )

    await message.answer(welcome_text, reply_markup=builder.as_markup())
    await state.set_state(Registration.language_selection)


@router.callback_query(Registration.language_selection, F.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery, state: FSMContext):
    lang_code = callback.data.split("_")[1]
    await state.update_data(selected_lang=lang_code)

    msgs = {
        "uz": ("📱 <b>Ro'yxatdan o'tish</b>\n\nEntelli Store'dan foydalanish uchun telefon raqamingizni yuboring.", "Telefon raqamni yuborish"),
        "ru": ("📱 <b>Регистрация</b>\n\nПожалуйста, отправьте свой номер телефона.", "Отправить номер"),
        "en": ("📱 <b>Registration</b>\n\nPlease share your phone number to continue.", "Send Phone Number"),
    }
    text, btn_text = msgs[lang_code]

    phone_kb = ReplyKeyboardMarkup(
        keyboard=[[reply_btn("phone", btn_text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await callback.message.delete()
    await callback.message.answer(text, reply_markup=phone_kb)
    await state.set_state(Registration.phone_number)


@router.message(Registration.phone_number, F.contact)
async def phone_received(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    lang = data.get("selected_lang", "uz")
    ref_code = data.get("ref_code")

    # Referal kodi tekshirish — kim taklif qilganini topamiz
    referred_by = None
    if ref_code:
        from sqlalchemy import select
        ref_result = await session.execute(
            select(User).where(User.referral_code == ref_code)
        )
        ref_user = ref_result.scalar_one_or_none()
        if ref_user and ref_user.telegram_id != message.from_user.id:
            referred_by = ref_code
            # Prompt bo'yicha: srazu bonus berilmaydi (firibgarlik oldini olish)

    new_user = User(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        phone_number=message.contact.phone_number,
        language=lang,
        referral_code=_generate_referral_code(message.from_user.id),
        referred_by=referred_by,
    )
    session.add(new_user)
    await session.commit()

    success_msg = {
        "uz": "✅ <b>Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!</b>\n\nAsosiy menyuni ochish uchun /start bosing.",
        "ru": "✅ <b>Регистрация успешно завершена!</b>\n\nНажмите /start чтобы открыть главное меню.",
        "en": "✅ <b>Registration completed successfully!</b>\n\nPress /start to open the main menu.",
    }

    await message.answer(success_msg[lang], reply_markup=ReplyKeyboardRemove())
    await state.clear()


# ───────────────────────────────────────────
# INLINE MENU CALLBACK HANDLERS
# ───────────────────────────────────────────

@router.callback_query(F.data == "menu_shop")
async def menu_shop(callback: CallbackQuery, session: AsyncSession, db_user: User, _: Callable[[str], str]):
    from bot.handlers.shop import show_shop
    await show_shop(callback, session, db_user, _)
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery, session: AsyncSession, db_user: User, _: Callable[[str], str]):
    from bot.handlers.profile import show_profile
    await show_profile(callback, session, db_user)
    await callback.answer()


@router.callback_query(F.data == "menu_balance")
async def menu_balance(callback: CallbackQuery, db_user: User):
    from bot.handlers.balance import show_balance_menu
    await show_balance_menu(callback, db_user)
    await callback.answer()


@router.callback_query(F.data == "menu_useful")
async def menu_useful(callback: CallbackQuery):
    from bot.handlers.useful import show_useful
    await show_useful(callback)
    await callback.answer()


@router.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery, session: AsyncSession, db_user: User):
    from bot.handlers.referral import show_referral
    await show_referral(callback, session, db_user)
    await callback.answer()


@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery):
    from core.config import config
    await callback.answer(url=config.SUPPORT_URL)


@router.callback_query(F.data == "menu_admin")
async def menu_admin(callback: CallbackQuery):
    from bot.handlers.admin.base import admin_menu
    await admin_menu(callback.message)
    await callback.answer()
