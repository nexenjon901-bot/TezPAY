import asyncio
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.config import config

async def test():
    bot = Bot(token=config.BOT_TOKEN.get_secret_value())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Do'kon", callback_data="shop", icon_custom_emoji_id="5373052667671093676")],
        [InlineKeyboardButton(text="Profil", callback_data="profile", icon_custom_emoji_id="5373012449597335010")],
        [InlineKeyboardButton(text="Balans to'ldirish", callback_data="bal", icon_custom_emoji_id="5271900303745110752")],
    ])
    try:
        await bot.send_message(chat_id=config.ADMIN_ID, text="Sinov: Tugmalarda Premium Emoji icon!", reply_markup=kb)
        print("Tugmalar muvaffaqiyatli yuborildi!")
    except Exception as e:
        print(f"Xatolik: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test())
