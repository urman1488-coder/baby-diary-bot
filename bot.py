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
# Теперь храним и тип действия для умного удаления дублей
recent_messages = defaultdict(lambda: deque(maxlen=10))

# Временное хранилище для выбранной каши (чтобы знать, к какой каше добавлять масло)
user_selected_porridge = {}

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

# Функция для удаления дублирующих сообщений бота с учетом типа действия
async def delete_bot_duplicates(chat_id: int, new_text: str, new_message_id: int, action_type: str = None):
    """
    Проверяет и инициирует удаление дублирующих сообщений бота в чате
    action_type - тип действия ('feeding', 'poop', 'sleep', 'porridge', 'vegetable', 'fruit', 'medicine')
    """
    current_time = datetime.now(MOSCOW_TZ)
    chat_messages = recent_messages[chat_id]
    
    logger.info(f"🔍 Проверка сообщения на дубль в чате {chat_id}, тип: {action_type}")
    
    for msg in chat_messages:
        time_diff = (current_time - msg["time"]).seconds
        text_match = msg["text"] == new_text
        type_match = msg.get("action_type") == action_type if action_type else False
        
        # Для дубля нужно совпадение И текста И типа действия в течение 120 секунд
        if time_diff < 120 and text_match and type_match:
            logger.info(f"  🚨 НАЙДЕН ДУБЛЬ! Разница {time_diff} сек, тип: {action_type}")
            asyncio.create_task(delayed_delete(chat_id, new_message_id, delay=10))
            return True
    
    # Если дублей не найдено, сохраняем это сообщение с типом действия
    logger.info(f"✅ Новое сообщение сохранено, тип: {action_type}")
    chat_messages.append({
        "text": new_text,
        "time": current_time,
        "message_id": new_message_id,
        "action_type": action_type
    })
    
    return False

# Функция отправки сообщения с автодудалением дублей
async def send_message_with_dedup(chat_id: int, text: str, reply_markup=None, action_type: str = None):
    """Отправляет сообщение и проверяет на дубли с учетом типа действия"""
    sent_message = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    is_duplicate = await delete_bot_duplicates(chat_id, text, sent_message.message_id, action_type)
    if is_duplicate:
        logger.info(f"🔄 Сообщение определено как дубль, будет удалено через 10 сек")
        return None
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
        reply_markup=get_keyboard(),
        action_type="welcome"
    )
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "🍼 Кормление")
async def log_feeding(message: types.Message):
    time = get_moscow_time()
    next_time = get_next_feeding_time()
    await send_message_with_dedup(
        message.chat.id,
        f"🍼 Кормление в {time}\n🕒 Следующее кормление в {next_time}",
        action_type="feeding"
    )
    asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))

@dp.message(F.text == "💩 Покакал")
async def log_poop(message: types.Message):
    time = get_moscow_time()
    await send_message_with_dedup(
        message.chat.id, 
        f"💩 Покакал в {time}",
        action_type="poop"
    )
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
            reply_markup=keyboard,
            action_type="sleep_start"
        )
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке сна: {e}")
        await send_message_with_dedup(message.chat.id, "❌ Произошла ошибка при записи сна")

# ========== ОБРАБОТЧИК ПРИКОРМА (ВАРИАНТ 4) ==========

@dp.message(F.text == "🥣 Прикорм")
async def log_porridge_start(message: types.Message):
    """Шаг 1: Выбор категории прикорма"""
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🥣 Каши", callback_data="porridge:category:porridge")],
                [InlineKeyboardButton(text="🥦 Овощи", callback_data="porridge:category:vegetables")],
                [InlineKeyboardButton(text="🍎 Фрукты", callback_data="porridge:category:fruits")]
            ]
        )
        
        await send_message_with_dedup(
            message.chat.id,
            "🥣 Выберите категорию прикорма:",
            reply_markup=keyboard,
            action_type="porridge_category"
        )
        
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе категории: {e}")
        await send_message_with_dedup(message.chat.id, "❌ Произошла ошибка")

# Обработчик выбора категории
@dp.callback_query(F.data.startswith("porridge:category:"))
async def handle_porridge_category(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    
    try:
        category = callback.data.split(":")[2]
        
        if category == "porridge":
            # Кнопки для каш
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔸 Гречневая", callback_data="porridge:select:buckwheat")],
                    [InlineKeyboardButton(text="🌾 Рисовая", callback_data="porridge:select:rice")],
                    [InlineKeyboardButton(text="🌽 Кукурузная", callback_data="porridge:select:corn")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="porridge:back:start")]
                ]
            )
            await callback.message.edit_text("🥣 Выберите кашу:", reply_markup=keyboard)
            
        elif category == "vegetables":
            # Кнопки для овощей
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🥦 Брокколи", callback_data="porridge:vegetable:broccoli")],
                    [InlineKeyboardButton(text="🥒 Кабачок", callback_data="porridge:vegetable:zucchini")],
                    [InlineKeyboardButton(text="🎃 Тыква", callback_data="porridge:vegetable:pumpkin")],
                    [InlineKeyboardButton(text="🥬 Цветная капуста", callback_data="porridge:vegetable:cauliflower")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="porridge:back:start")]
                ]
            )
            await callback.message.edit_text("🥦 Выберите овощное пюре:", reply_markup=keyboard)
            
        elif category == "fruits":
            # Кнопки для фруктов
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🍎 Яблоко", callback_data="porridge:fruit:apple")],
                    [InlineKeyboardButton(text="🍐 Груша", callback_data="porridge:fruit:pear")],
                    [InlineKeyboardButton(text="🍌 Банан", callback_data="porridge:fruit:banana")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="porridge:back:start")]
                ]
            )
            await callback.message.edit_text("🍎 Выберите фруктовое пюре:", reply_markup=keyboard)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Обработчик выбора каши
@dp.callback_query(F.data.startswith("porridge:select:"))
async def handle_porridge_select(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    
    try:
        porridge_type = callback.data.split(":")[2]
        
        # Сохраняем выбранную кашу для пользователя
        user_selected_porridge[callback.from_user.id] = porridge_type
        
        # Кнопки для выбора масла
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🫒 Оливковое", callback_data="porridge:oil:olive")],
                [InlineKeyboardButton(text="🌻 Подсолнечное", callback_data="porridge:oil:sunflower")],
                [InlineKeyboardButton(text="🧈 Сливочное", callback_data="porridge:oil:butter")],
                [InlineKeyboardButton(text="⏭️ Без масла", callback_data="porridge:oil:none")],
                [InlineKeyboardButton(text="◀️ Назад к кашам", callback_data="porridge:back:porridge")]
            ]
        )
        
        # Определяем название каши
        porridge_names = {
            "buckwheat": "Гречневая каша",
            "rice": "Рисовая каша",
            "corn": "Кукурузная каша"
        }
        porridge_name = porridge_names.get(porridge_type, "Каша")
        
        await callback.message.edit_text(
            f"🥣 {porridge_name}\n\n🥄 Добавить масло:",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Обработчик выбора масла - ИСПРАВЛЕНО (только редактирование)
@dp.callback_query(F.data.startswith("porridge:oil:"))
async def handle_oil_select(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    
    try:
        oil_type = callback.data.split(":")[2]
        current_time = get_moscow_time()
        
        # Получаем выбранную ранее кашу
        porridge_type = user_selected_porridge.get(callback.from_user.id, "buckwheat")
        
        # Названия каш
        porridge_names = {
            "buckwheat": "Гречневая каша",
            "rice": "Рисовая каша",
            "corn": "Кукурузная каша"
        }
        porridge_name = porridge_names.get(porridge_type, "Каша")
        
        # Названия масел
        oil_names = {
            "olive": "🫒 оливковое масло",
            "sunflower": "🌻 подсолнечное масло",
            "butter": "🧈 сливочное масло",
            "none": ""
        }
        oil_name = oil_names.get(oil_type, "")
        
        # Формируем итоговое сообщение
        if oil_name:
            result_text = f"🥣 {porridge_name} + {oil_name}\n🕐 {current_time}"
        else:
            result_text = f"🥣 {porridge_name}\n🕐 {current_time}"
        
        # Очищаем сохраненную кашу
        if callback.from_user.id in user_selected_porridge:
            del user_selected_porridge[callback.from_user.id]
        
        # ✅ ТОЛЬКО РЕДАКТИРУЕМ, НЕ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ
        await callback.message.edit_text(result_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Обработчик выбора овощей - ИСПРАВЛЕНО (только редактирование)
@dp.callback_query(F.data.startswith("porridge:vegetable:"))
async def handle_vegetable_select(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    
    try:
        vegetable_type = callback.data.split(":")[2]
        current_time = get_moscow_time()
        
        vegetable_names = {
            "broccoli": "🥦 Брокколи",
            "zucchini": "🥒 Кабачок",
            "pumpkin": "🎃 Тыква",
            "cauliflower": "🥬 Цветная капуста"
        }
        vegetable_name = vegetable_names.get(vegetable_type, "Овощное пюре")
        
        result_text = f"{vegetable_name} в {current_time}"
        
        # ✅ ТОЛЬКО РЕДАКТИРУЕМ, НЕ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ
        await callback.message.edit_text(result_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Обработчик выбора фруктов - ИСПРАВЛЕНО (только редактирование)
@dp.callback_query(F.data.startswith("porridge:fruit:"))
async def handle_fruit_select(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    
    try:
        fruit_type = callback.data.split(":")[2]
        current_time = get_moscow_time()
        
        fruit_names = {
            "apple": "🍎 Яблоко",
            "pear": "🍐 Груша",
            "banana": "🍌 Банан"
        }
        fruit_name = fruit_names.get(fruit_type, "Фруктовое пюре")
        
        result_text = f"{fruit_name} в {current_time}"
        
        # ✅ ТОЛЬКО РЕДАКТИРУЕМ, НЕ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ
        await callback.message.edit_text(result_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Обработчик кнопки "Назад"
@dp.callback_query(F.data.startswith("porridge:back:"))
async def handle_porridge_back(callback: types.CallbackQuery):
    callback_id = f"{callback.message.chat.id}:{callback.message.message_id}:{callback.data}"
    if callback_id in processed_callbacks:
        await callback.answer()
        return
    processed_callbacks.add(callback_id)
    
    try:
        back_to = callback.data.split(":")[2]
        
        if back_to == "start":
            # Возврат к выбору категории
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🥣 Каши", callback_data="porridge:category:porridge")],
                    [InlineKeyboardButton(text="🥦 Овощи", callback_data="porridge:category:vegetables")],
                    [InlineKeyboardButton(text="🍎 Фрукты", callback_data="porridge:category:fruits")]
                ]
            )
            await callback.message.edit_text("🥣 Выберите категорию прикорма:", reply_markup=keyboard)
            
        elif back_to == "porridge":
            # Возврат к выбору каш
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔸 Гречневая", callback_data="porridge:select:buckwheat")],
                    [InlineKeyboardButton(text="🌾 Рисовая", callback_data="porridge:select:rice")],
                    [InlineKeyboardButton(text="🌽 Кукурузная", callback_data="porridge:select:corn")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="porridge:back:start")]
                ]
            )
            await callback.message.edit_text("🥣 Выберите кашу:", reply_markup=keyboard)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# ========== КОНЕЦ ОБРАБОТЧИКА ПРИКОРМА ==========

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
            reply_markup=keyboard,
            action_type="medicine_menu"
        )
        asyncio.create_task(delete_user_message_with_retry(message.chat.id, message.message_id))
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе лекарства: {e}")

# Обработчики callback'ов для лекарств - ИСПРАВЛЕНО (только редактирование)
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
        
        # ✅ ТОЛЬКО РЕДАКТИРУЕМ, НЕ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ
        await callback.message.edit_text(result_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Обработчик callback'ов для сна - ИСПРАВЛЕНО (только редактирование)
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
        
        # ✅ ТОЛЬКО РЕДАКТИРУЕМ, НЕ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ
        await callback.message.edit_text(result_text)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Настройка вебхуков
async def on_startup(app):
    processed_callbacks.clear()
    processed_updates.clear()
    recent_messages.clear()
    user_selected_porridge.clear()
    
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

# Health check endpoints
async def health_check(request):
    return web.Response(text="Bot is running")

app.router.add_get('/health', health_check)
app.router.add_get('/', health_check)
app.router.add_get('/ping', health_check)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    logger.info(f"🚀 Запуск бота на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
