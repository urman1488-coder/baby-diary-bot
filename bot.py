import os
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"
MSK_TZ = pytz.timezone("Europe/Moscow")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Клавиатура
keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.row("🍼 Кормление", "💩 Покакал")
keyboard.row("😴 Сон", "🤮 Срыгивание", "💊 Витамин D")

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "👶 Дневник активности ребёнка готов!\n\nНажимайте кнопки для записи событий:",
        reply_markup=keyboard
    )

@dp.message_handler()
async def handle_button(message: types.Message):
    valid_buttons = ["🍼 Кормление", "💩 Покакал", "😴 Сон", "🤮 Срыгивание", "💊 Витамин D"]
    if message.text in valid_buttons:
        time_now = datetime.now(MSK_TZ).strftime("%H:%M")
        await message.answer(f"{message.text} в {time_now}", reply_markup=keyboard)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
