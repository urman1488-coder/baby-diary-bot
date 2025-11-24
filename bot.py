import logging
from datetime import datetime, timedelta
import pytz
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
        "👶 Дневник ребёнка\n\nВыберите действие на клавиатуре:",
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

@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    try:
        current_time = datetime.now(MOSCOW_TZ)
        timestamp = int(current_time.timestamp())
        
        # Создаем inline-кнопку с временем начала сна
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👶 Проснулся", 
                        callback_data=f"wakeup:{timestamp}"
                    )
                ]
            ]
        )
        
        sent_message = await message.answer(
            f"😴 Уснул в {current_time.strftime('%H:%M')}\n"
            "Нажмите кнопку ниже, когда ребёнок проснётся.",
            reply_markup=keyboard
        )
        
        # Сохраняем ID сообщения для возможного обновления
        logger.info(f"✅ Сообщение с inline-кнопкой отправлено. ID: {sent_message.message_id}")
        
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке сна: {e}")
        await message.answer("❌ Произошла ошибка при записи сна")

# Обработчик нажатия на inline-кнопку (упрощенная версия)
@dp.callback_query()
async def handle_all_callbacks(callback: types.CallbackQuery):
    try:
        logger.info(f"📨 Получен callback: {callback.data}")
        
        if callback.data.startswith("wakeup:"):
            # Извлекаем время начала сна из callback_data
            timestamp_str = callback.data.split(":")[1]
            sleep_start = datetime.fromtimestamp(int(timestamp_str), MOSCOW_TZ)
            wake_time = datetime.now(MOSCOW_TZ)
            
            # Корректируем дату, если сон перешел через полночь
            if wake_time < sleep_start:
                wake_time = wake_time + timedelta(days=1)
            
            duration = wake_time - sleep_start
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            # Обновляем сообщение с результатом
            try:
                await callback.message.edit_text(
                    f"💤 Сон: {sleep_start.strftime('%H:%M')} - {wake_time.strftime('%H:%M')}\n"
                    f"⏱ Длительность: {hours} часов {minutes} минут"
                )
                logger.info("✅ Сообщение успешно обновлено")
            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении сообщения: {e}")
                # Если не удалось обновить, отправляем новое сообщение
                await callback.message.answer(
                    f"💤 Сон: {sleep_start.strftime('%H:%M')} - {wake_time.strftime('%H:%M')}\n"
                    f"⏱ Длительность: {hours} часов {minutes} минут"
                )
            
            # Всегда отвечаем на callback
            await callback.answer("✅ Пробуждение зафиксировано!")
            
        else:
            await callback.answer("❌ Неизвестная команда")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике callback: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

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
        
        # Логируем тип обновления для диагностики
        if update.callback_query:
            logger.info(f"📨 Обработка callback запроса: {update.callback_query.data}")
        elif update.message:
            logger.info(f"📨 Обработка сообщения: {update.message.text}")
        
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
