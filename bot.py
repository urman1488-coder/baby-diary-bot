import os
import logging
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота
BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Создание клавиатуры
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🍼 Кормление"),
            KeyboardButton(text="💩 Покакал")
        ],
        [
            KeyboardButton(text="😴 Сон"),
            KeyboardButton(text="🤮 Срыгивание")
        ],
        [
            KeyboardButton(text="💊 Витамин D")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Функция для получения текущего времени по МСК
def get_moscow_time():
    return datetime.now(MOSCOW_TZ).strftime("%H:%M")

# Обработчики кнопок
@dp.message_handler(lambda message: message.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🍼 Кормление в {time}")

@dp.message_handler(lambda message: message.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💩 Покакал в {time}")

@dp.message_handler(lambda message: message.text == "😴 Сон")
async def log_sleep(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"😴 Сон в {time}")

@dp.message_handler(lambda message: message.text == "🤮 Срыгивание")
async def log_spitup(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🤮 Срыгивание в {time}")

@dp.message_handler(lambda message: message.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💊 Витамин D в {time}")

# Стартовое сообщение
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.answer(
        "👶 Дневник ребёнка\n\n"
        "Выберите действие на клавиатуре:",
        reply_markup=keyboard
    )

# Запуск бота
if __name__ == '__main__':
    logging.info("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
