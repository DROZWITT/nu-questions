import os
import json
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
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

PORT = int(os.environ.get("PORT", 10000))

WEBHOOK_URL = "https://nu-questions-1.onrender.com"

# ID группы
GROUP_ID = -1003466972957


# 🔹 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    text="📨 Открыть форму запроса",
                    web_app=WebAppInfo(url=WEBHOOK_URL)
                )
            ]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "Нажмите кнопку ниже, чтобы отправить запрос:",
        reply_markup=keyboard,
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
    thread_id = data.get("thread_id", 4)  # 🔥 Тема №4

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


# 🔹 Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))

    print(f"🚀 Бот запускается на порту {PORT}...")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )
