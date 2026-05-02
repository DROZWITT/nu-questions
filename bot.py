import os
import json
import logging
import threading
import re
import time
import asyncio
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# Логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не установлен!")

GROUP_ID = -1003466972957

# 👇 СПИСОК ID АДМИНОВ
ADMIN_IDS = [8060757101, 637540883, 750506022] 

# --- НАСТРОЙКИ АНТИСПАМА ---
user_last_request = {} 
COOLDOWN_SECONDS = 300  # 5 минут
# ---------------------------

# --- 🔥 УМНЫЙ ФИЛЬТР МАТА (БАЗА BARS38) 🔥 ---
def download_dictionary(url):
    """Скачивает список слов и превращает в set для мгновенного поиска"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # Превращаем в set (множество) для мгновенного поиска
        return set(word.strip().lower() for word in response.text.split('\n') if word.strip())
    except Exception as e:
        logging.error(f"Не удалось скачать словарь {url}: {e}")
        return set()

# Прямая RAW-ссылка на файл из репозитория bars38
BARS38_URL = "https://raw.githubusercontent.com/bars38/Russian_ban_words/master/words.txt"

# Загружаем базу при старте
print("📥 Загрузка базы мата bars38...")
BAN_WORDS_SET = download_dictionary(BARS38_URL)
if not BAN_WORDS_SET:
    # Запасной вариант, если GitHub отвалится
    BAN_WORDS_SET = {'хуй', 'пизда', 'ебать', 'шлюха', 'гандон', 'сука', 'блядь'}
print(f"✅ Загружено {len(BAN_WORDS_SET)} плохих слов из базы bars38!")

# Оставляем турецкий/английский мат отдельным списком для поиска по корням
FOREIGN_AND_TRANSLIT_ROOTS = [
    'amk', 'sik', 'yarrak', 'orospu', 'göt', 'pezevenk', 'fahişe', 'jalep', 'dalbayop',
    'huy', 'hui', 'xuy', 'blyat', 'bliat', 'suka', 'syka', 'pidor', 'pidar', 'gandon', 'gondon', 'ebat', 'eblan', 'zalu', 'mudak', 'shluha', 'shlyuha'
]

def normalize_text(text):
    """Снимает маскировку с текста (замена a на а, 0 на о и т.д.)"""
    text = text.lower()
    replacements = {
        'a': 'а', 'b': 'в', 'c': 'с', 'e': 'е', 'h': 'н', 
        'k': 'к', 'm': 'м', 'o': 'о', 'p': 'р', 't': 'т', 
        'x': 'х', 'y': 'у', '0': 'о', '3': 'з', '4': 'ч', '@': 'а'
    }
    for lat, cyr in replacements.items():
        text = text.replace(lat, cyr)
        
    # Удаляем все знаки препинания, оставляем только буквы (п.и.з.д.а -> пизда)
    text = re.sub(r'[^а-яёa-z\s]', '', text)
    return text

def has_profanity(text):
    """Финальная проверка текста"""
    normalized_text = normalize_text(text)
    words = normalized_text.split()
    
    for word in words:
        # 1. Проверка по гигантской базе bars38 (мгновенно!)
        if word in BAN_WORDS_SET:
            return True
            
        # 2. Проверка транслита и иностранного мата по корням
        for root in FOREIGN_AND_TRANSLIT_ROOTS:
            if root in word:
                return True
                
    return False
# ------------------------------------------


# 🔹 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.message

    if chat.type in ["group", "supergroup"]:
        if message.message_thread_id != 4:
            return

        group_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="✉️ Заполнить заявку", url="https://t.me/LigoRecords_bot")]]
        )
        await message.reply_text(
            "Для отправки запроса перейдите в личные сообщения со мной:",
            reply_markup=group_keyboard,
        )
        return

    private_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(text="📨 Открыть форму запроса", web_app=WebAppInfo(url="https://nu-questions-1.onrender.com"))]],
        resize_keyboard=True
    )
    await message.reply_text("Нажмите кнопку ниже, чтобы отправить запрос:", reply_markup=private_keyboard)


# 🔹 Обработка WebApp (Получение заявки)
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.web_app_data:
        return

    user_id = update.message.from_user.id 

    # --- АНТИСПАМ ПРОЦЕСС ---
    current_time = time.time()
    last_time = user_last_request.get(user_id, 0)

    if current_time - last_time < COOLDOWN_SECONDS:
        time_left = int(COOLDOWN_SECONDS - (current_time - last_time))
        minutes = time_left // 60
        seconds = time_left % 60
        
        await update.message.reply_text(
            f"⏳ <b>Не так быстро!</b>\n"
            f"Следующий запрос можно будет отправить через {minutes} мин. {seconds} сек.",
            parse_mode='HTML'
        )
        return 
    # ------------------------

    try:
        data = json.loads(update.message.web_app_data.data)
    except Exception as e:
        print("Ошибка JSON:", e)
        return

    name = data.get("name", "Не указано")
    issue = data.get("issue", "Не указано")

    # ❗️ ПРОВЕРКА НА МАТ (НОВЫЙ ФИЛЬТР)
    if has_profanity(name) or has_profanity(issue):
        await update.message.reply_text(
            "🤬 <b>Запрос отклонен!</b>\n"
            "В вашем сообщении обнаружена ненормативная лексика или оскорбления. Пожалуйста, переформулируйте ваш вопрос культурно.",
            parse_mode='HTML'
        )
        return 
    # ---------------------------------

    user_last_request[user_id] = current_time
    thread_id = data.get("thread_id", 4)

    text_to_group = (
        "📩 <b>Новый запрос</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"🆔 ID: {user_id}\n\n"
        f"📝 <b>Вопрос:</b>\n{issue}\n\n"
        "💬 <i>Для отправки запроса нажмите кнопку ниже:</i>"
    )

    try:
        group_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="✉️ Заполнить заявку", url="https://t.me/LigoRecords_bot")],
            [InlineKeyboardButton(text="👤 Написать в ЛС (Только админам)", callback_data=f"pm_{user_id}")]
        ])
        
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=text_to_group,
            message_thread_id=thread_id,
            parse_mode='HTML',
            reply_markup=group_keyboard
        )
        
        await update.message.reply_text("✅ Ваш запрос отправлен! Ожидайте ответа от администрации.")

    except Exception as e:
        print("Ошибка отправки:", e)
        await update.message.reply_text("❌ Ошибка отправки.")

# 🔹 Обработчик скрытой кнопки для Админов
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await query.answer("⛔️ Эта кнопка доступна только администраторам!", show_alert=True)
        return
        
    if query.data.startswith("pm_"):
        target_user_id = query.data.split("_")[1]
        profile_url = f"tg://user?id={target_user_id}"
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"👤 <b>Пользователь из заявки:</b>\n<a href='{profile_url}'>👉 Нажмите сюда, чтобы перейти к нему в личные сообщения</a>",
                parse_mode='HTML'
            )
            await query.answer("✅ Ссылка на профиль отправлена вам в личные сообщения бота!", show_alert=True)
        except Exception as e:
            logging.error(f"Не удалось отправить в ЛС админу: {e}")
            await query.answer("❌ Ошибка! Бот не может написать вам. Сначала отправьте боту в ЛС команду /start", show_alert=True)


# 🔹 Обработка ответов админов из группы
async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if not message.reply_to_message:
        return
    if message.reply_to_message.from_user.id != context.bot.id:
        return

    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text:
        return

    match = re.search(r"🆔 ID:\s*(\d+)", original_text)
    if not match:
        return
        
    user_id = int(match.group(1))

    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )
        await message.reply_text("✅ Ответ отправлен пользователю!", quote=True)
    except Exception as e:
        logging.error(f"Ошибка при отправке: {e}")
        await message.reply_text("❌ Не удалось отправить ответ. Возможно, пользователь заблокировал бота.", quote=True)


# --- Простой сервер-заглушка для Render ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()


# 🔹 Запуск
if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))
    
    app.add_handler(CallbackQueryHandler(admin_callback_handler))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.REPLY, admin_reply_handler))

    print("🚀 Бот запущен через polling (с поддержкой порта для Render)...")

    app.run_polling()
