import asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from core.config import config

async def test():
    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode="HTML")
    )
    # Admin ID ga to'g'ridan-to'g'ri custom emoji bilan xabar yuborib ko'ramiz
    text = (
        'Test custom emoji:\n'
        '<tg-emoji emoji-id="5373052667671093676">🛍️</tg-emoji> Do\'kon\n'
        '<tg-emoji emoji-id="5373012449597335010">👤</tg-emoji> Profil\n'
        '<tg-emoji emoji-id="5271900303745110752">💰</tg-emoji> Balans'
    )
    try:
        msg = await bot.send_message(chat_id=config.ADMIN_ID, text=text)
        print("Muvaffaqiyatli yuborildi! Message entities:")
        for ent in (msg.entities or []):
            print(f"Type: {ent.type}, custom_emoji_id: {getattr(ent, 'custom_emoji_id', None)}")
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test())
