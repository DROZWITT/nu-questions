import os
import json
from telegram import (
    Update,
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = "https://nu-questions.onrender.com"

# ID твоей группы
GROUP_ID = -1003466972957


# 🔹 КНОПКА ОТКРЫТИЯ WEBAPP
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="📨 Открыть форму",
                web_app=WebAppInfo(
                    url="https://nu-questions.onrender.com/index.html"
                ),
            )
        ]
    ])

    await update.message.reply_text(
        "Нажми кнопку ниже, чтобы отправить вопрос:",
        reply_markup=keyboard,
    )


# 🔹 ОБРАБОТКА ДАННЫХ ИЗ WEBAPP
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.web_app_data:
        return

    data = json.loads(update.message.web_app_data.data)

    name = data.get("name")
    issue = data.get("issue")
    user_id = data.get("user_id")

    text = (
        "📩 Новый запрос\n\n"
        f"👤 Имя: {name}\n"
        f"📝 Вопрос:\n{issue}\n\n"
        f"🆔 ID: {user_id}"
    )

    await context.bot.send_message(chat_id=GROUP_ID, text=text)
    await update.message.reply_text("✅ Ваш запрос отправлен!")


app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))


if __name__ == "__main__":
    print("Бот запущен через webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )
