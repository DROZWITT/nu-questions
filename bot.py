import os
import json
import logging
import threading
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
        # Если пишут не в 4-ю тему, бот просто промолчит
        if message.message_thread_id != 4:
            return

        # В группах Telegram не разрешает отправлять данные из WebApp напрямую боту.
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


# 🔹 Обработка WebApp
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
    user_id = data.get("user_id", "Неизвестно")
    thread_id = data.get("thread_id", 4)  # Тема №4

    text_to_group = (
        "📩 Новый запрос\n\n"
        f"👤 Имя: {name}\n"
        f"🆔 ID: {user_id}\n\n"
        f"📝 Вопрос:\n{issue}"
    )

    try:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=text_to_group,
            message_thread_id=thread_id
        )

        await update.message.reply_text("✅ Ваш запрос отправлен в тему №4!")

    except Exception as e:
        print("Ошибка отправки:", e)
        await update.message.reply_text("❌ Ошибка отправки.")


# --- Простой сервер-заглушка для Render ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    # Render автоматически задает переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()


# 🔹 Запуск
if __name__ == "__main__":
    # Запускаем фейковый веб-сервер в фоновом потоке, чтобы Render видел открытый порт
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))

    print("🚀 Бот запущен через polling (с поддержкой порта для Render)...")

    app.run_polling()
