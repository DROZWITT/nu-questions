import os
import json
import logging
import threading
import re
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

# ID группы
GROUP_ID = -1003466972957


# 🔹 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.message

    # --- 1. Логика для ГРУППЫ ---
    if chat.type in ["group", "supergroup"]:
        if message.message_thread_id != 4:
            return

        group_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="✉️ Заполнить заявку",
                        url="https://t.me/LigoRecords_bot"
                    )
                ]
            ]
        )
        await message.reply_text(
            "Для отправки запроса перейдите в личные сообщения со мной:",
            reply_markup=group_keyboard,
        )
        return

    # --- 2. Логика для ЛИЧНЫХ СООБЩЕНИЙ ---
    private_keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    text="📨 Открыть форму запроса",
                    web_app=WebAppInfo(url="https://nu-questions-1.onrender.com")
                )
            ]
        ],
        resize_keyboard=True
    )

    await message.reply_text(
        "Нажмите кнопку ниже, чтобы отправить запрос:",
        reply_markup=private_keyboard,
    )


# 🔹 Обработка WebApp (Получение заявки)
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.web_app_data:
        return

    try:
        data = json.loads(update.message.web_app_data.data)
    except Exception as e:
        print("Ошибка JSON:", e)
        return

    name = data.get("name", "Не указано")
    issue = data.get("issue", "Не указано")
    user_id = update.message.from_user.id 
    thread_id = data.get("thread_id", 4)  # Тема №4

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
        await update.message.reply_text("✅ Ваш запрос отправлен! Ожидайте ответа.")

    except Exception as e:
        print("Ошибка отправки:", e)
        await update.message.reply_text("❌ Ошибка отправки.")


# 🔹 Обработка ответов админов из группы
async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    # 1. Проверяем, что это ответ на сообщение
    if not message.reply_to_message:
        return
        
    # 2. Проверяем, что отвечают именно на сообщение бота
    if message.reply_to_message.from_user.id != context.bot.id:
        return

    # 3. Пытаемся найти ID пользователя в сообщении, на которое отвечаем
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text:
        return

    # Ищем строчку "🆔 ID: 12345678"
    match = re.search(r"🆔 ID:\s*(\d+)", original_text)
    if not match:
        return # Это было сообщение бота, но не заявка
        
    user_id = int(match.group(1))

    # 4. Пересылаем ответ админа пользователю в личку
    try:
        # Копируем сообщение, чтобы поддерживались фото, видео, файлы и текст
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )
        # Ставим реакцию или пишем, что всё ок
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

    # Регистрируем команды и обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))
    
    # ❗️ Новый обработчик для перехвата ваших ответов в группе (работает только в группе GROUP_ID)
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.REPLY, admin_reply_handler))

    print("🚀 Бот запущен через polling (с поддержкой порта для Render)...")

    app.run_polling()
