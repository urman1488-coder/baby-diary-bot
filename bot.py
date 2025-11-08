import os
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"
MSK_TZ = pytz.timezone("Europe/Moscow")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(
    KeyboardButton("🍼 Кормление"),
    KeyboardButton("💩 Покакал"),
    KeyboardButton("😴 Сон"),
    KeyboardButton("🤮 Срыгивание"),
    KeyboardButton("💊 Витамин D")
)

@dp.message_handler(lambda msg: msg.text in [btn.text for row in keyboard.keyboard for btn in row])
async def handle_button(message: types.Message):
    time_now = datetime.now(MSK_TZ).strftime("%H:%M")
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"{message.text} в {time_now}",
        reply_markup=keyboard
    )

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
