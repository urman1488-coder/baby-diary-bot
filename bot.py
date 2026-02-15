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
recent_messages = defaultdict(lambda: deque(maxlen=5))  # Храним последние 5 сообщений в чате

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

# Функция для удаления дублирующих сообщений бота (5 секунд)
async def delete_bot_duplicates(chat_id: int, new_text: str, new_message_id: int):
    """
    Проверяет и удаляет дублирующие сообщения бота в чате
    Удаляет ТОЛЬКО если:
    1. Сообщение отправлено в последние 5 секунд
    2. Текст полностью совпадает
    """
    current_time = datetime.now(MOSCOW_TZ)
    
    # Получаем последние сообщения в этом чате
    chat_messages = recent_messages[chat_id]
    
    # Логируем для отладки
    logger.info(f"🔍 Проверка сообщения на дубль в чате {chat_id}")
    
    # Ищем похожие сообщения за последние 5 секунд
    for msg in chat_messages:
        time_diff = (current_time - msg["time"]).seconds
        text_match = msg["text"] == new_text
        
        # Если нашли похожее сообщение за последние 5 секунд
        if time_diff < 5 and text_match:  # ИЗМЕНЕНО: 15 -> 5 секунд
            logger.info(f"  🚨 НАЙДЕН ДУБЛЬ! Разница {time_diff} сек < 5 сек")
            
            # Удаляем новое (дублирующее) сообщение
            try:
                await bot.delete_message(chat_id, new_message_id)
                logger.info(f"  ✅ Дубль удален (ID: {new_message_id})")
                return True  # Сообщение было дублем и удалено
            except Exception as e:
                logger.error(f"  ❌ Не удалось удалить дубль: {e}")
                return False
        else:
            if time_diff >= 5:
                logger.info(f"  ⏭️ Сообщение старше 5 сек ({time_diff} сек) - не дубль")
            if not text_match:
                logger.info(f"  📝 Текст разный - не дубль")
    
    # Если дублей не найдено, сохраняем это сообщение
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
    # Отправляем сообщение
    sent_message = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    
    # Проверяем, не дубль ли это
    is_duplicate = await delete_bot_duplicates(chat_id, text, sent_message.message_id)
    
    if is_duplicate:
        logger.info(f"🔄 Сообщение было дублем и удалено")
        return None
    else:
        return sent_message

# Функция удаления сообщения пользователя
async def delete_user_message_with_retry(chat_id: int, message_id: int, max_attempts: int = 3):
    """Удаляет сообщение пользователя с повторными попытками"""
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

# Обработчик сна с inline-кнопкой
@dp.message(F.text == "😴 Сон")
async def log_sleep(message: types.Message):
    try:
        current_time = datetime.now(MOSCOW_TZ)
        timestamp = int(current_time.timestamp())
        
        # Создаем inline-кнопку с временем начала сна в callback_data
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

# Обработчик прикорма с inline-кнопками выбора каши
@dp.message(F.text == "🥣 Прикорм")
async def log_porridge(message: types.Message):
    try:
        # Создаем inline-кнопки для выбора типа каши
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

# Обработчик лекарств с inline-кнопками выбора лекарства
@dp.message(F.text == "💊 Лекарства/Витамины")
async def log_medicine(message: types.Message):
    try:
        # Создаем inline-кнопки для выбора лекарства
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

# Обработчик нажатия на inline-кнопку выбора каши
@dp.callback_query(F.data.startswith("porridge:"))
async def handle_porridge_callback(callback: types.CallbackQuery):
    try:
        # Создаем уникальный идентификатор для этого callback
        callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
        
        # Проверяем, не обрабатывали ли мы уже этот callback
        if callback_id in processed_callbacks:
            logger.info(f"🔄 Пропускаем дублирующий callback: {callback_id}")
            await callback.answer()
            return
            
        # Добавляем callback в список обработанных
        processed_callbacks.add(callback_id)
        logger.info(f"📨 Обрабатываем callback выбора каши")
        
        # Получаем текущее время
        current_time = get_moscow_time()
        
        # Определяем тип каши по callback_data
        porridge_type = callback.data.split(":")[1]
        
        if porridge_type == "buckwheat":
            porridge_name = "Гречневая каша"
        elif porridge_type == "rice":
            porridge_name = "Рисовая каша"
        elif porridge_type == "corn":
            porridge_name = "Кукурузная каша"
        else:
            porridge_name = "Каша"
        
        # Формируем текст результата
        result_text = f"🥣 {porridge_name} в {current_time}"
        
        # Пытаемся отредактировать сообщение
        try:
            await callback.message.edit_text(result_text)
            logger.info(f"✅ Сообщение о прикорме отредактировано")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение с защитой от дублей
            await send_message_with_dedup(callback.message.chat.id, result_text)
        
        # Подтверждаем обработку callback
        await callback.answer()
        logger.info("✅ Callback выбора каши успешно обработан")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике выбора каши: {e}")
        await callback.answer("❌ Произошла ошибка при записи прикорма", show_alert=True)

# Обработчик нажатия на inline-кнопку выбора лекарства
@dp.callback_query(F.data.startswith("medicine:"))
async def handle_medicine_callback(callback: types.CallbackQuery):
    try:
        # Создаем уникальный идентификатор для этого callback
        callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
        
        # Проверяем, не обрабатывали ли мы уже этот callback
        if callback_id in processed_callbacks:
            logger.info(f"🔄 Пропускаем дублирующий callback: {callback_id}")
            await callback.answer()
            return
            
        # Добавляем callback в список обработанных
        processed_callbacks.add(callback_id)
        logger.info(f"📨 Обрабатываем callback выбора лекарства")
        
        # Получаем текущее время
        current_time = get_moscow_time()
        
        # Определяем тип лекарства по callback_data
        medicine_type = callback.data.split(":")[1]
        
        if medicine_type == "vitamin_d":
            medicine_name = "💊 Витамин D"
        elif medicine_type == "candle":
            medicine_name = "🕯️ Свеча при температуре"
        elif medicine_type == "iron":
            medicine_name = "🧲 Железо"
        else:
            medicine_name = "💊 Лекарство"
        
        # Формируем текст результата
        result_text = f"{medicine_name} в {current_time}"
        
        # Пытаемся отредактировать сообщение
        try:
            await callback.message.edit_text(result_text)
            logger.info(f"✅ Сообщение о лекарстве отредактировано")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение с защитой от дублей
            await send_message_with_dedup(callback.message.chat.id, result_text)
        
        # Подтверждаем обработку callback
        await callback.answer()
        logger.info("✅ Callback выбора лекарства успешно обработан")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике выбора лекарства: {e}")
        await callback.answer("❌ Произошла ошибка при записи лекарства", show_alert=True)

# Обработчик нажатия на inline-кнопку сна
@dp.callback_query(F.data.startswith("wakeup:"))
async def handle_wakeup_callback(callback: types.CallbackQuery):
    try:
        # Создаем уникальный идентификатор для этого callback
        callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
        
        # Проверяем, не обрабатывали ли мы уже этот callback
        if callback_id in processed_callbacks:
            logger.info(f"🔄 Пропускаем дублирующий callback: {callback_id}")
            await callback.answer()
            return
            
        # Добавляем callback в список обработанных
        processed_callbacks.add(callback_id)
        logger.info(f"📨 Обрабатываем callback пробуждения")
        
        # Извлекаем timestamp из callback_data
        timestamp_str = callback.data.split(":")[1]
        sleep_start = datetime.fromtimestamp(int(timestamp_str), MOSCOW_TZ)
        wake_time = datetime.now(MOSCOW_TZ)
        
        # Рассчитываем длительность сна
        duration = wake_time - sleep_start
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        # Формируем текст результата
        result_text = (
            f"💤 Сон: с {sleep_start.strftime('%H:%M')} до {wake_time.strftime('%H:%M')}\n"
            f"⏱ Длительность: {hours} часов {minutes} минут"
        )
        
        # Пытаемся отредактировать сообщение
        try:
            await callback.message.edit_text(result_text)
            logger.info("✅ Сообщение о сне отредактировано")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение с защитой от дублей
            await send_message_with_dedup(callback.message.chat.id, result_text)
        
        # Подтверждаем обработку callback
        await callback.answer()
        logger.info("✅ Callback пробуждения успешно обработан")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике пробуждения: {e}")
        await callback.answer("❌ Произошла ошибка при обработке пробуждения", show_alert=True)

# Настройка вебхуков
async def on_startup(app):
    # Очищаем все хранилища при запуске
    processed_callbacks.clear()
    processed_updates.clear()
    recent_messages.clear()
    
    # Удаляем старый вебхук и все ожидающие обновления
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Устанавливаем новый вебхук
    await bot.set_webhook(
        WEBHOOK_URL,
        allowed_updates=["message", "callback_query"],
        max_connections=5,  # Ограничиваем соединения для уменьшения дублей
        drop_pending_updates=True
    )
    logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    logger.info("✅ Разрешены обновления: message, callback_query")

async def handle_webhook(request):
    try:
        token = request.match_info.get('token')
        if token != BOT_TOKEN:
            logger.warning(f"❌ Неверный токен: {token}")
            return web.Response(status=403)
        
        update_data = await request.json()
        update_id = update_data.get("update_id")
        
        # Проверяем, не обрабатывали ли мы этот update_id
        if update_id in processed_updates:
            logger.info(f"🔄 Пропускаем дублирующий update_id: {update_id}")
            return web.Response(status=200)  # Отвечаем 200, но не обрабатываем
        
        # Добавляем в обработанные
        processed_updates.append(update_id)
        
        update = types.Update(**update_data)
        
        # Логируем тип обновления
        if update.callback_query:
            logger.info(f"📨 Вебхук: получен callback_query")
        elif update.message:
            logger.info(f"📨 Вебхук: получено сообщение")
        
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
app.router.add_get('/ping', health_check)  # Для keep-alive

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    logger.info(f"🚀 Запуск бота на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
