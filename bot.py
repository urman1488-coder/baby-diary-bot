import logging
from datetime import datetime
import pytz
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота и настройки
BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"
WEBHOOK_HOST = 'https://your-bot-name.onrender.com'  # ЗАМЕНИТЕ на ваш реальный URL Render
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

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

# Функция для получения текущего времени по МСК
def get_moscow_time():
    return datetime.now(MOSCOW_TZ).strftime("%H:%M")

# Функция для удаления сообщения пользователя через 10 секунд
async def delete_user_message_after_delay(chat_id: int, message_id: int):
    await asyncio.sleep(10)
    try:
        await bot.delete_message(chat_id, message_id)
        logger.info("✅ Сообщение пользователя удалено")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить сообщение пользователя: {e}")

# Обработчики сообщений
@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    await message.answer(
        "👶 Дневник ребёнка\n\nВыберите действие на клавиатуре:",
        reply_markup=get_keyboard()
    )
    asyncio.create_task(delete_user_message_after_delay(message.chat.id, message.message_id))

@dp.message(F.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🍼 Кормление в {time}")
    asyncio.create_task(delete_user_message_after_delay(message.chat.id, message.message_id))

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💩 Покакал в {time}")
    asyncio.create_task(delete_user_message_after_delay(message.chat.id, message.message_id))

@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"😴 Сон в {time}")
    asyncio.create_task(delete_user_message_after_delay(message.chat.id, message.message_id))

@dp.message(F.text == "🤮 Срыгивание")
async def log_spitup(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🤮 Срыгивание в {time}")
    asyncio.create_task(delete_user_message_after_delay(message.chat.id, message.message_id))

@dp.message(F.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💊 Витамин D в {time}")
    asyncio.create_task(delete_user_message_after_delay(message.chat.id, message.message_id))

# Настройка вебхуков
async def on_startup(app):
    # Устанавливаем вебхук при запуске
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    else:
        logger.info("✅ Вебхук уже установлен")

async def handle_webhook(request):
    """Обработчик входящих вебхуков от Telegram"""
    try:
        # Проверяем, что запрос содержит JSON
        update_data = await request.json()
        update = types.Update(**update_data)
        
        # Передаем обновление в диспетчер
        await dp.feed_webhook_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        return web.Response(status=500)

# Создание приложения
app = web.Application()
app.router.add_post(f'/webhook/{BOT_TOKEN}', handle_webhook)

# Добавляем startup хук
app.on_startup.append(on_startup)

# Health check endpoint
async def health_check(request):
    return web.Response(text="Bot is running")

app.router.add_get('/health', health_check)

if __name__ == '__main__':
    # Запуск при запуске скрипта
    port = int(os.environ.get('PORT', 3000))
    web.run_app(app, host='0.0.0.0', port=port)
