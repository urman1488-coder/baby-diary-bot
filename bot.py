import logging
from datetime import datetime
import pytz
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Функция для получения текущего времени по МСК
def get_moscow_time():
    return datetime.now(MOSCOW_TZ).strftime("%H:%M")

# Создание клавиатуры
def get_keyboard():
    return ReplyKeyboardMarkup(
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
        resize_keyboard=True
    )

# Функция для быстрого ответа и удаления сообщения пользователя
async def quick_response(message: types.Message, text: str):
    # Сначала удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение: {e}")
    
    # Затем отправляем ответ
    await message.answer(text)

# Основное меню
@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    await quick_response(message,
        "👶 Дневник ребёнка\n\n"
        "Нажмите на кнопку чтобы записать событие:\n\n"
        "🍼 Кормление\n"
        "💩 Покакал\n"  
        "😴 Сон\n"
        "🤮 Срыгивание\n"
        "💊 Витамин D"
    )

# Обработчики событий
@dp.message(F.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    await quick_response(message, f"🍼 Кормление в {time}")

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await quick_response(message, f"💩 Покакал в {time}")

@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    time = get_moscow_time()
    await quick_response(message, f"😴 Сон в {time}")

@dp.message(F.text == "🤮 Срыгивание")
async def log_spitup(message: types.Message):
    time = get_moscow_time()
    await quick_response(message, f"🤮 Срыгивание в {time}")

@dp.message(F.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await quick_response(message, f"💊 Витамин D в {time}")

# Запуск бота
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
