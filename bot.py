import os
import json
import logging
import threading
import re
import time
import requests  # ❗️ Добавили библиотеку для скачивания словарей
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

# --- НАСТРОЙКИ АНТИСПАМА ---
user_last_request = {} 
COOLDOWN_SECONDS = 300  # 5 минут
# ---------------------------

# --- НАСТРОЙКИ ЦЕНЗУРЫ И СЛОВАРЕЙ ---
def download_dictionary(url, default_list):
    """Скачивает список слов по ссылке"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return [line.strip().lower() for line in response.text.split('\n') if line.strip()]
    except Exception as e:
        logging.error(f"Не удалось скачать словарь {url}: {e}")
        return default_list

# Прямые ссылки на словари
URL_CURSE = "https://raw.githubusercontent.com/ddfdi/russian_ban_words/main/ru_curse_words.txt"
URL_ABUSIVE = "https://raw.githubusercontent.com/ddfdi/russian_ban_words/main/ru_abusive_words.txt"
URL_EXCEPT = "https://raw.githubusercontent.com/ddfdi/russian_ban_words/main/ru_exception_words.txt"

# Скачиваем словари при запуске
CURSE_WORDS = download_dictionary(URL_CURSE, ['хуй', 'пизд', 'ебат'])
ABUSIVE_WORDS = download_dictionary(URL_ABUSIVE, ['дурак', 'идиот', 'дебил'])

# ❗️ Объединяем мат и легкие оскорбления в один огромный список
FORBIDDEN_WORDS = CURSE_WORDS + ABUSIVE_WORDS
EXCEPTION_WORDS = download_dictionary(URL_EXCEPT, ['оскорблять', 'употреблять', 'расслабляться', 'колебаться'])

def has_profanity(text):
    """Проверка текста на мат и оскорбления с учетом исключений"""
    text_lower = text.lower()
    
    # 1. Заменяем слова-исключения на пробелы
    for exc in EXCEPTION_WORDS:
        text_lower = text_lower.replace(exc, ' ')
        
    # 2. Проверяем очищенный текст по объединенной базе
    for word in FORBIDDEN_WORDS:
        if word in text_lower:
            return True
            
    return False
# ------------------------------------


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

    # ❗️ ПРОВЕРКА НА МАТ И ОСКОРБЛЕНИЯ
    if has_profanity(name) or has_profanity(issue):
        await update.message.reply_text(
            "🤬 <b>Запрос отклонен!</b>\n"
            "В вашем сообщении обнаружена ненормативная лексика или оскорбления. Пожалуйста, переформулируйте ваш вопрос культурно.",
            parse_mode='HTML'
        )
        return 
    # ---------------------------------

    # Обновляем таймер антиспама только если сообщение прошло цензуру
    user_last_request[user_id] = current_time
    thread_id = data.get("thread_id", 4)

    text_to_group = (
        "📩 <b>Новый запрос</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"🆔 ID: {user_id}\n\n"
        f"📝 <b>Вопрос:</b>\n{issue}"
    )

    try:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=text_to_group,
            message_thread_id=thread_id,
            parse_mode='HTML'
        )
        await update.message.reply_text("✅ Ваш запрос отправлен! Ожидайте ответа от администрации.")

    except Exception as e:
        print("Ошибка отправки:", e)
        await update.message.reply_text("❌ Ошибка отправки.")


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
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.REPLY, admin_reply_handler))

    print("🚀 Бот запущен через polling (с поддержкой порта для Render)...")

    app.run_polling()
