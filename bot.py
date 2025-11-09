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

# Токен бота и настройки вебхука
BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"
WEBHOOK_HOST = 'https://baby-diary-bot-1.onrender.com'  # ВАШ РЕАЛЬНЫЙ URL
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота
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

# Обработчики команд
@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    await message.answer(
        "👶 Дневник ребёнка\n\nВыберите действие на клавиатуре:",
        reply_markup=get_keyboard()
    )

@dp.message(F.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🍼 Кормление в {time}")

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💩 Покакал в {time}")

@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"😴 Сон в {time}")

@dp.message(F.text == "🤮 Срыгивание")
async def log_spitup(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🤮 Срыгивание в {time}")

@dp.message(F.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💊 Витамин D в {time}")

# Настройка вебхуков
async def on_startup(app):
    # Устанавливаем вебхук при запуске
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")

async def handle_webhook(request):
    """Обработчик входящих вебхуков от Telegram"""
    try:
        # Проверяем токен в URL
        token = request.match_info.get('token')
        if token != BOT_TOKEN:
            return web.Response(status=403)
        
        # Обрабатываем обновление
        update_data = await request.json()
        update = types.Update(**update_data)
        await dp.feed_webhook_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        return web.Response(status=500)

# Создание приложения
app = web.Application()
app.router.add_post('/webhook/{token}', handle_webhook)
app.on_startup.append(on_startup)

# Health check endpoint
async def health_check(request):
    return web.Response(text="Bot is running")

app.router.add_get('/health', health_check)
app.router.add_get('/', health_check)

if __name__ == '__main__':
    # Запуск веб-сервера
    port = int(os.environ.get('PORT', 3000))
    web.run_app(app, host='0.0.0.0', port=port)
