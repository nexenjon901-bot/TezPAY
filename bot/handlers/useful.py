from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.emoji import pe, btn_args

router = Router()

USEFUL_LINKS = [
    ("📺 YouTube kanalimiz", "https://youtube.com/@entelli4ever?si=iO8-vSUT117rRk8c"),
    ("💬 Telegram kanalimiz", "https://t.me/entellistore"),
]


async def show_useful(target):
    builder = InlineKeyboardBuilder()
    for name, url in USEFUL_LINKS:
        builder.button(text=name, url=url)
    builder.button(**btn_args("back", "Orqaga"), callback_data="menu_back")
    builder.adjust(1)

    text = (
        f"{pe('useful')} <b>Foydali havolalar</b>\n\n"
        "<blockquote>"
        "Quyidagi havolalar orqali biz bilan bog'laning va "
        "eng so'nggi yangiliklar, aksiyalar bilan tanishib boring!"
        "</blockquote>"
    )

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text=text, reply_markup=builder.as_markup())
        except Exception:
            await target.message.answer(text, reply_markup=builder.as_markup())
    else:
        await target.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery):
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
        await callback.message.edit_text(text=text, reply_markup=get_main_menu_keyboard(lambda x: x, is_admin=is_admin))
    except Exception:
        await callback.message.answer(text, reply_markup=get_main_menu_keyboard(lambda x: x, is_admin=is_admin))
    await callback.answer()
