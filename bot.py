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

# Улучшенная функция для удаления сообщений с повторными попытками
async def delete_user_message_safe(chat_id: int, message_id: int, max_retries: int = 3):
    """Безопасное удаление сообщения пользователя с повторными попытками"""
    for attempt in range(max_retries):
        try:
            await bot.delete_message(chat_id, message_id)
            logger.info(f"✅ Сообщение пользователя {message_id} удалено")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}: не удалось удалить сообщение пользователя {message_id}. Ошибка: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)  # Ждем 2 секунды перед повторной попыткой
    logger.error(f"❌ Не удалось удалить сообщение пользователя {message_id} после {max_retries} попыток")
    return False

# Функция для обработки сообщений - удаляет только сообщения пользователя через 10 секунд
async def handle_user_message(message: types.Message, response_text: str):
    """Отправляет ответ и удаляет сообщение пользователя через 10 секунд"""
    user_message_id = message.message_id
    chat_id = message.chat.id
    
    # Отправляем ответ бота (не удаляем его)
    bot_response = await message.answer(response_text)
    
    # Ждем 10 секунд и пытаемся удалить сообщение пользователя
    await asyncio.sleep(10)
    
    # Пытаемся удалить сообщение пользователя
    await delete_user_message_safe(chat_id, user_message_id)

# Основное меню
@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    await handle_user_message(message,
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
    await handle_user_message(message, f"🍼 Кормление в {time}")

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await handle_user_message(message, f"💩 Покакал в {time}")

@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    time = get_moscow_time()
    await handle_user_message(message, f"😴 Сон в {time}")

@dp.message(F.text == "🤮 Срыгивание")
async def log_spitup(message: types.Message):
    time = get_moscow_time()
    await handle_user_message(message, f"🤮 Срыгивание в {time}")

@dp.message(F.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await handle_user_message(message, f"💊 Витамин D в {time}")

# Команда для тестирования
@dp.message(Command("test"))
async def test_cleanup(message: types.Message):
    await handle_user_message(message, "🧪 Тестовое сообщение - сообщение пользователя удалится через 10 секунд, это сообщение останется")

# Обработка любых других сообщений (если пользователь пишет текст вместо кнопок)
@dp.message()
async def other_messages(message: types.Message):
    await handle_user_message(message, 
        "Пожалуйста, используйте кнопки на клавиатуре для записи событий.\n\n"
        "Если клавиатура не отображается, отправьте /start"
    )

# Запуск бота
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
