import asyncio
from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from core.config import config

async def test():
    bot = Bot(token=config.BOT_TOKEN.get_secret_value())
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Statistika", icon_custom_emoji_id="5433982607035474385")],
            [KeyboardButton(text="Do'kon", icon_custom_emoji_id="5373052667671093676")]
        ],
        resize_keyboard=True
    )
    try:
        await bot.send_message(chat_id=config.ADMIN_ID, text="Sinov: ReplyKeyboard'da icon_custom_emoji_id!", reply_markup=kb)
        print("Reply keyboard muvaffaqiyatli yuborildi!")
    except Exception as e:
        print(f"Xatolik: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test())
