import os
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"
MSK_TZ = pytz.timezone("Europe/Moscow")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍼 Кормление"), KeyboardButton(text="💩 Покакал")],
        [KeyboardButton(text="😴 Сон"), KeyboardButton(text="🤮 Срыгивание")],
        [KeyboardButton(text="💊 Витамин D")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("👶 Дневник активности ребёнка готов!\n\nНажимайте кнопки для записи событий:", reply_markup=keyboard)

@dp.message()
async def handle_button(message: Message):
    if message.text in ["🍼 Кормление", "💩 Покакал", "😴 Сон", "🤮 Срыгивание", "💊 Витамин D"]:
        time_now = datetime.now(MSK_TZ).strftime("%H:%M")
        await message.answer(f"{message.text} в {time_now}", reply_markup=keyboard)

if __name__ == "__main__":
    dp.run_polling(bot)
