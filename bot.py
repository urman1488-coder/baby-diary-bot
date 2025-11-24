import logging
from datetime import datetime, timedelta
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
WEBHOOK_HOST = 'https://baby-diary-bot-1.onrender.com'
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Словарь для хранения времени начала сна
sleep_start_times = {}

# Создание клавиатуры
def get_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🍼 Кормление"),
                KeyboardButton(text="💩 Покакал")
            ],
            [
                KeyboardButton(text="😴 Уснул"),
                KeyboardButton(text="👶 Проснулся")
            ],
            [
                KeyboardButton(text="🤮 Срыгивание"),
                KeyboardButton(text="💊 Витамин D")
            ]
        ],
        resize_keyboard=True
    )

# Функция для получения текущего времени по МСК
def get_moscow_time():
    return datetime.now(MOSCOW_TZ).strftime("%H:%M")

# Функция для получения времени следующего кормления (+3 часа)
def get_next_feeding_time():
    next_time = datetime.now(MOSCOW_TZ) + timedelta(hours=3)
    return next_time.strftime("%H:%M")

# Функция для удаления сообщения пользователя с повторными попытками
async def delete_user_message_with_retry(chat_id: int, message_id: int, max_attempts: int = 3):
    """Удаляет сообщение пользователя с повторными попытками в случае ошибки"""
    for attempt in range(1, max_attempts + 1):
        try:
            await asyncio.sleep(10)
            await bot.delete_message(chat_id, message_id)
            logger.info(f"✅ Сообщение пользователя удалено (попытка {attempt})")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить сообщение пользователя (попытка {attempt}): {e}")
            if attempt < max_attempts:
                await asyncio.sleep(5)
    
    logger.error(f"❌ Не удалось удалить сообщение пользователя после {max_attempts} попыток")
    return False

# Обработчики команд
@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    await message.answer(
        "👶 Дневник ребёнка\n\n"
        "Выберите действие на клавиатуре:",
        reply_markup=get_keyboard()
    )
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    next_time = get_next_feeding_time()
    await message.answer(f"🍼 Кормление в {time}\n🕒 Следующее кормление в {next_time}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💩 Покакал в {time}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "😴 Уснул")
async def log_sleep(message: types.Message):
    chat_id = str(message.chat.id)
    current_time = datetime.now(MOSCOW_TZ)
    
    # Сохраняем время начала сна
    sleep_start_times[chat_id] = current_time
    time_str = current_time.strftime("%H:%M")
    
    await message.answer(f"😴 Уснул в {time_str}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "👶 Проснулся")
async def log_wakeup(message: types.Message):
    chat_id = str(message.chat.id)
    current_time = datetime.now(MOSCOW_TZ)
    
    if chat_id not in sleep_start_times:
        await message.answer("⚠️ Сон не был начат! Нажмите '😴 Уснул' когда ребёнок уснет.")
    else:
        sleep_start = sleep_start_times[chat_id]
        sleep_end = current_time
        duration = sleep_end - sleep_start
        
        # Форматируем время
        start_str = sleep_start.strftime("%H:%M")
        end_str = sleep_end.strftime("%H:%M")
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        await message.answer(f"👶 Проснулся в {end_str} ⏱ Спал {hours}ч {minutes}м")
        
        # Удаляем запись о начале сна
        del sleep_start_times[chat_id]
    
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "🤮 Срыгивание")
async def log_spitup(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"🤮 Срыгивание в {time}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💊 Витамин D в {time}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

# Настройка вебхуков
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")

async def handle_webhook(request):
    try:
        token = request.match_info.get('token')
        if token != BOT_TOKEN:
            return web.Response(status=403)
        
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
    port = int(os.environ.get('PORT', 3000))
    web.run_app(app, host='0.0.0.0', port=port)
