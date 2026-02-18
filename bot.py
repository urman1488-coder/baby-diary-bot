import logging
from datetime import datetime, timedelta
import pytz
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiohttp import web
import os
from collections import deque, defaultdict

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токен бота и настройки вебхука
BOT_TOKEN = "8547013591:AAF4aeK79jP4Gt7-GFWjcT8_O2KVb4yRKcI"
WEBHOOK_HOST = 'https://baby-diary-bot-1.onrender.com'
WEBHOOK_PATH = f'/webhook/{BOT_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Хранилище обработанных update_id (защита от дублей на уровне вебхука)
processed_updates = deque(maxlen=200)

# Словарь для отслеживания обработанных callback'ов
processed_callbacks = set()

# Словарь для отслеживания последних отправленных сообщений бота
# Структура: {chat_id: [{"text": text, "time": datetime, "message_id": id}]}
recent_messages = defaultdict(lambda: deque(maxlen=10))  # Храним последние 10 сообщений в чате

# Создание клавиатуры
def get_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🍼 Кормление"),
                KeyboardButton(text="🥣 Прикорм")
            ],
            [
                KeyboardButton(text="😴 Сон"),
                KeyboardButton(text="💩 Покакал")
            ],
            [
                KeyboardButton(text="💊 Лекарства/Витамины")
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

# Функция отложенного удаления дублирующего сообщения
async def delayed_delete(chat_id: int, message_id: int, delay: int = 10):
    """Удаляет сообщение через указанное количество секунд"""
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id, message_id)
        logger.info(f"✅ Дубль удалён через {delay} сек (ID: {message_id})")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить дубль (ID: {message_id}): {e}")

# Функция для удаления дублирующих сообщений бота (120 секунд, удаление через 10 сек)
async def delete_bot_duplicates(chat_id: int, new_text: str, new_message_id: int):
    """
    Проверяет и инициирует удаление дублирующих сообщений бота в чате
    Удаляет ТОЛЬКО если:
    1. Сообщение отправлено в последние 120 секунд
    2. Текст полностью совпадает
    Удаление происходит через 10 секунд после отправки дубля.
    """
    current_time = datetime.now(MOSCOW_TZ)
    
    # Получаем последние сообщения в этом чате
    chat_messages = recent_messages[chat_id]
    
    logger.info(f"🔍 Проверка сообщения на дубль в чате {chat_id}")
    
    # Ищем похожие сообщения за последние 120 секунд
    for msg in chat_messages:
        time_diff = (current_time - msg["time"]).seconds
        text_match = msg["text"] == new_text
        
        if time_diff < 120 and text_match:  # Окно 120 секунд
            logger.info(f"  🚨 НАЙДЕН ДУБЛЬ! Разница {time_diff} сек < 120 сек")
            
            # Не сохраняем дубль в историю, запускаем отложенное удаление
            asyncio.create_task(delayed_delete(chat_id, new_message_id, delay=10))
            return True  # Сообщение было дублем
    
    # Если дублей не найдено, сохраняем это сообщение в историю
    logger.info(f"✅ Новое сообщение (не дубль) сохранено в истории")
    chat_messages.append({
        "text": new_text,
        "time": current_time,
        "message_id": new_message_id
    })
    
    return False  # Это не дубль

# Функция отправки сообщения с автодудалением дублей
async def send_message_with_dedup(chat_id: int, text: str, reply_markup=None):
    """
    Отправляет сообщение и проверяет на дубли
    """
    sent_message = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    is_duplicate = await delete_bot_duplicates(chat_id, text, sent_message.message_id)
    if is_duplicate:
        logger.info(f"🔄 Сообщение определено как дубль, будет удалено через 10 сек")
        return None
    else:
        return sent_message

# Функция удаления сообщения пользователя
async def delete_user_message_with_retry(chat_id: int, message_id: int, max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            await asyncio.sleep(5)
            await bot.delete_message(chat_id, message_id)
            logger.info(f"✅ Сообщение пользователя удалено")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt}: {e}")
            if attempt < max_attempts:
                await asyncio.sleep(2)
    logger.error(f"❌ Не удалось удалить сообщение пользователя")
    return False

# Обработчики команд
@dp.message(Command("start", "help"))
async def send_welcome(message: types.Message):
    await send_message_with_dedup(
        message.chat.id, 
        "👶 Дневник ребёнка\n\nВыберите действие на клавиатуре:",
        reply_markup=get_keyboard()
    )
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    next_time = get_next_feeding_time()
    await send_message_with_dedup(
        message.chat.id,
        f"🍼 Кормление в {time}\n🕒 Следующее кормление в {next_time}"
    )
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await send_message_with_dedup(message.chat.id, f"💩 Покакал в {time}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    try:
        current_time = datetime.now(MOSCOW_TZ)
        timestamp = int(current_time.timestamp())
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👶 Проснулся", callback_data=f"wakeup:{timestamp}")]
            ]
        )
        await send_message_with_dedup(
            message.chat.id,
            f"😴 Уснул в {current_time.strftime('%H:%M')}\n"
            "Нажмите кнопку ниже, когда ребёнок проснётся.",
            reply_markup=keyboard
        )
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке сна: {e}")
        await send_message_with_dedup(message.chat.id, "❌ Произошла ошибка при записи сна")

@dp.message(F.text == "🥣 Прикорм")
async def log_porridge(message: types.Message):
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔸 Гречневая", callback_data="porridge:buckwheat"),
                    InlineKeyboardButton(text="🌾 Рисовая", callback_data="porridge:rice")
                ],
                [
                    InlineKeyboardButton(text="🌽 Кукурузная", callback_data="porridge:corn")
                ]
            ]
        )
        await send_message_with_dedup(
            message.chat.id,
            "🥣 Выберите тип каши:",
            reply_markup=keyboard
        )
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе прикорма: {e}")
        await send_message_with_dedup(message.chat.id, "❌ Произошла ошибка при выборе прикорма")

@dp.message(F.text == "💊 Лекарства/Витамины")
async def log_medicine(message: types.Message):
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💊 Витамин D", callback_data="medicine:vitamin_d")],
                [InlineKeyboardButton(text="🕯️ Свеча при температуре", callback_data="medicine:candle")],
                [InlineKeyboardButton(text="🧲 Железо", callback_data="medicine:iron")]
            ]
        )
        await send_message_with_dedup(
            message.chat.id,
            "💊 Выберите лекарство:",
            reply_markup=keyboard
        )
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе лекарства: {e}")
        await send_message_with_dedup(message.chat.id, "❌ Произошла ошибка при выборе лекарства")

# Обработчики callback'ов
@dp.callback_query(F.data.startswith("porridge:"))
async def handle_porridge_callback(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    try:
        current_time = get_moscow_time()
        porridge_type = callback.data.split(":")[1]
        porridge_names = {
            "buckwheat": "Гречневая каша",
            "rice": "Рисовая каша",
            "corn": "Кукурузная каша"
        }
        porridge_name = porridge_names.get(porridge_type, "Каша")
        result_text = f"🥣 {porridge_name} в {current_time}"
        try:
            await callback.message.edit_text(result_text)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать: {e}")
            await send_message_with_dedup(callback.message.chat.id, result_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("medicine:"))
async def handle_medicine_callback(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    try:
        current_time = get_moscow_time()
        medicine_type = callback.data.split(":")[1]
        medicine_names = {
            "vitamin_d": "💊 Витамин D",
            "candle": "🕯️ Свеча при температуре",
            "iron": "🧲 Железо"
        }
        medicine_name = medicine_names.get(medicine_type, "💊 Лекарство")
        result_text = f"{medicine_name} в {current_time}"
        try:
            await callback.message.edit_text(result_text)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать: {e}")
            await send_message_with_dedup(callback.message.chat.id, result_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("wakeup:"))
async def handle_wakeup_callback(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    try:
        timestamp_str = callback.data.split(":")[1]
        sleep_start = datetime.fromtimestamp(int(timestamp_str), MOSCOW_TZ)
        wake_time = datetime.now(MOSCOW_TZ)
        duration = wake_time - sleep_start
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        result_text = (
            f"💤 Сон: с {sleep_start.strftime('%H:%M')} до {wake_time.strftime('%H:%M')}\n"
            f"⏱ Длительность: {hours} часов {minutes} минут"
        )
        try:
            await callback.message.edit_text(result_text)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать: {e}")
            await send_message_with_dedup(callback.message.chat.id, result_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Настройка вебхуков
async def on_startup(app):
    processed_callbacks.clear()
    processed_updates.clear()
    recent_messages.clear()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(
        WEBHOOK_URL,
        allowed_updates=["message", "callback_query"],
        max_connections=5,
        drop_pending_updates=True
    )
    logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")

async def handle_webhook(request):
    try:
        token = request.match_info.get('token')
        if token != BOT_TOKEN:
            return web.Response(status=403)
        update_data = await request.json()
        update_id = update_data.get("update_id")
        if update_id in processed_updates:
            logger.info(f"🔄 Пропускаем дублирующий update_id: {update_id}")
            return web.Response(status=200)
        processed_updates.append(update_id)
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

# Health check endpoints (для cron-job.org)
async def health_check(request):
    """Эндпоинт для проверки здоровья бота и keep-alive"""
    return web.Response(text="Bot is running")

# Добавляем все необходимые endpoint'ы для пинга
app.router.add_get('/health', health_check)
app.router.add_get('/', health_check)
app.router.add_get('/ping', health_check)  # Основной endpoint для cron-job.org

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    logger.info(f"🚀 Запуск бота на порту {port}")
    logger.info(f"📌 Keep-alive endpoints:")
    logger.info(f"   - /ping")
    logger.info(f"   - /health")
    logger.info(f"   - /")
    web.run_app(app, host='0.0.0.0', port=port)
