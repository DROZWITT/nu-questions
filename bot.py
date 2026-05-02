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
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return set(word.strip().lower() for word in response.text.split('\n') if word.strip())
    except Exception as e:
        logging.error(f"Не удалось скачать словарь {url}: {e}")
        return set()

BARS38_URL = "https://raw.githubusercontent.com/bars38/Russian_ban_words/master/words.txt"
print("📥 Загрузка базы мата...")
BAN_WORDS_SET = download_dictionary(BARS38_URL)
if not BAN_WORDS_SET:
    BAN_WORDS_SET = {'хуй', 'пизда', 'ебать', 'шлюха', 'гандон', 'сука', 'блядь'}
print(f"✅ Загружено {len(BAN_WORDS_SET)} плохих слов!")

FOREIGN_AND_TRANSLIT_ROOTS = [
    'amk', 'sik', 'yarrak', 'orospu', 'göt', 'pezevenk', 'fahişe', 'jalep', 'dalbayop',
    'huy', 'hui', 'xuy', 'blyat', 'bliat', 'suka', 'syka', 'pidor', 'pidar', 'gandon', 'gondon', 'ebat', 'eblan', 'zalu', 'mudak', 'shluha', 'shlyuha'
]

def normalize_text(text):
    text = text.lower()
    replacements = {
        'a': 'а', 'b': 'в', 'c': 'с', 'e': 'е', 'h': 'н', 
        'k': 'к', 'm': 'м', 'o': 'о', 'p': 'р', 't': 'т', 
        'x': 'х', 'y': 'у', '0': 'о', '3': 'з', '4': 'ч', '@': 'а'
    }
    for lat, cyr in replacements.items():
        text = text.replace(lat, cyr)
    text = re.sub(r'[^а-яёa-z\s]', '', text)
    return text

def has_profanity(text):
    normalized_text = normalize_text(text)
    words = normalized_text.split()
    for word in words:
        if word in BAN_WORDS_SET:
            return True
        for root in FOREIGN_AND_TRANSLIT_ROOTS:
            if root in word:
                return True
    return False


# 🔹 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.message
    if chat.type in ["group", "supergroup"]:
        if message.message_thread_id != 4: return
        group_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text="✉️ Заполнить заявку", url="https://t.me/LigoRecords_bot")]])
        await message.reply_text("Для отправки запроса перейдите в личные сообщения со мной:", reply_markup=group_keyboard)
        return
    private_keyboard = ReplyKeyboardMarkup([[KeyboardButton(text="📨 Открыть форму запроса", web_app=WebAppInfo(url="https://nu-questions-1.onrender.com"))]], resize_keyboard=True)
    await message.reply_text("Нажмите кнопку ниже, чтобы отправить запрос:", reply_markup=private_keyboard)


# 🔹 Обработка WebApp (Получение заявки)
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.web_app_data: return
    user_id = update.message.from_user.id 
    current_time = time.time()
    last_time = user_last_request.get(user_id, 0)

    if current_time - last_time < COOLDOWN_SECONDS:
        time_left = int(COOLDOWN_SECONDS - (current_time - last_time))
        await update.message.reply_text(f"⏳ <b>Не так быстро!</b>\nСледующий запрос через {time_left // 60} мин.", parse_mode='HTML')
        return 

    try:
        data = json.loads(update.message.web_app_data.data)
    except: return

    name, issue = data.get("name", "Не указано"), data.get("issue", "Не указано")
    if has_profanity(name) or has_profanity(issue):
        await update.message.reply_text("🤬 <b>Запрос отклонен!</b>\nСоблюдайте цензуру.", parse_mode='HTML')
        return 

    user_last_request[user_id] = current_time
    thread_id = data.get("thread_id", 4)
    text_to_group = f"📩 <b>Новый запрос</b>\n\n👤 <b>Имя:</b> {name}\n🆔 ID: {user_id}\n\n📝 <b>Вопрос:</b>\n{issue}\n\n💬 <i>Для связи используйте кнопку или ответьте на это сообщение:</i>"

    try:
        group_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="✉️ Заполнить заявку", url="https://t.me/LigoRecords_bot")]
        ])
        await context.bot.send_message(chat_id=GROUP_ID, text=text_to_group, message_thread_id=thread_id, parse_mode='HTML', reply_markup=group_keyboard)
        await update.message.reply_text("✅ Ваш запрос отправлен!")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка отправки.")


# 🔹 Обработка ответов админов (С АВТО-ССЫЛКОЙ В ЛС)
async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    admin_id = message.from_user.id # ID админа, который отвечает
    
    if not message.reply_to_message or message.reply_to_message.from_user.id != context.bot.id:
        return

    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text: return

    match = re.search(r"🆔 ID:\s*(\d+)", original_text)
    if not match: return
    user_id = int(match.group(1))

    try:
        # 1. Отправляем ответ пользователю
        await context.bot.copy_message(chat_id=user_id, from_chat_id=message.chat_id, message_id=message.message_id)
        await message.reply_text("✅ Ответ отправлен пользователю!", quote=True)
        
        # 2. Сразу даем админу ссылку на профиль в его ЛС с ботом
        profile_url = f"tg://user?id={user_id}"
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔗 <b>Вы ответили на запрос пользователя {user_id}</b>\n\n"
                     f"Если нужно продолжить общение лично:\n"
                     f"<a href='{profile_url}'>👉 Перейти к диалогу с ним</a>",
                parse_mode='HTML'
            )
        except:
            pass # Если админ не запустил бота в ЛС, просто пропускаем

    except Exception as e:
        await message.reply_text("❌ Ошибка отправки (возможно, бот заблокирован).", quote=True)


# --- Простой сервер для Render ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"Alive")

def run_dummy_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), DummyHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.REPLY, admin_reply_handler))
    print("🚀 Бот запущен!")
    app.run_polling()
