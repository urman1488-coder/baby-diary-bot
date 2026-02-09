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

# Словарь для отслеживания обработанных callback'ов (защита от дублирования)
processed_callbacks = set()

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
                KeyboardButton(text="🥣 Прикорм")
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
        
        await message.answer(
            f"😴 Уснул в {current_time.strftime('%H:%M')}\n"
            "Нажмите кнопку ниже, когда ребёнок проснётся.",
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Сообщение с inline-кнопкой отправлено. Время начала сна: {current_time.strftime('%H:%M')}")
        
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке сна: {e}")
        await message.answer("❌ Произошла ошибка при записи сна")

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
        
        await message.answer(
            "🥣 Выберите тип каши:",
            reply_markup=keyboard
        )
        
        logger.info("✅ Сообщение с выбором каши отправлено")
        
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе прикорма: {e}")
        await message.answer("❌ Произошла ошибка при выборе прикорма")

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
        logger.info(f"📨 Обрабатываем callback выбора каши: {callback_id}")
        
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
        result_text = f"📝 Прикорм: {porridge_name}\n⏰ {current_time}"
        
        # Пытаемся отредактировать сообщение
        try:
            await callback.message.edit_text(result_text)
            logger.info(f"✅ Сообщение о прикорме отредактировано: {porridge_name}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            await callback.message.answer(result_text)
        
        # Подтверждаем обработку callback
        await callback.answer()
        logger.info("✅ Callback выбора каши успешно обработан")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике выбора каши: {e}")
        await callback.answer("❌ Произошла ошибка при записи прикорма", show_alert=True)

# Обработчик нажатия на inline-кнопку сна с защитой от дублирования
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
        logger.info(f"📨 Обрабатываем callback: {callback_id}")
        
        # Извлекаем timestamp из callback_data
        timestamp_str = callback.data.split(":")[1]
        sleep_start = datetime.fromtimestamp(int(timestamp_str), MOSCOW_TZ)
        wake_time = datetime.now(MOSCOW_TZ)
        
        # Рассчитываем длительность сна
        duration = wake_time - sleep_start
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        # Формируем текст результата в формате "с (время) до (время)"
        result_text = (
            f"💤 Сон: с {sleep_start.strftime('%H:%M')} до {wake_time.strftime('%H:%M')}\n"
            f"⏱ Длительность: {hours} часов {minutes} минут"
        )
        
        # Пытаемся отредактировать сообщение
        try:
            await callback.message.edit_text(result_text)
            logger.info("✅ Сообщение успешно отредактировано")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            await callback.message.answer(result_text)
        
        # Подтверждаем обработку callback
        await callback.answer()
        logger.info("✅ Callback успешно обработан")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике пробуждения: {e}")
        await callback.answer("❌ Произошла ошибка при обработке пробуждения", show_alert=True)

@dp.message(F.text == "💊 Витамин D")
async def log_vitamin_d(message: types.Message):
    time = get_moscow_time()
    await message.answer(f"💊 Витамин D в {time}")
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

# Настройка вебхуков
async def on_startup(app):
    # Очищаем список обработанных callback'ов при запуске
    processed_callbacks.clear()
    
    # Указываем allowed_updates для получения callback_query
    await bot.set_webhook(
        WEBHOOK_URL,
        allowed_updates=["message", "callback_query"]
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
        update = types.Update(**update_data)
        
        # Логируем тип обновления
        if update.callback_query:
            logger.info(f"📨 Вебхук: получен callback_query с данными: {update.callback_query.data}")
        elif update.message:
            logger.info(f"📨 Вебхук: получено сообщение: {update.message.text}")
        
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
    logger.info(f"🚀 Запуск бота на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
