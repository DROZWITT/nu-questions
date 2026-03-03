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
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не установлен!")

PORT = int(os.environ.get("PORT", 10000))

# ✅ ВАЖНО: должен совпадать с реальным URL Render
WEBHOOK_URL = "https://nu-questions-1.onrender.com"

# ⚠️ Пока оставим старый ID — позже проверим реальный
GROUP_ID = -1003466972957


# 🔹 DEBUG ДЛЯ ПОЛУЧЕНИЯ РЕАЛЬНОГО ID ГРУППЫ
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("REAL CHAT ID:", update.effective_chat.id)


# 🔹 КНОПКА ОТКРЫТИЯ WEBAPP
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.type != "private":
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="📨 Открыть форму запроса",
                web_app=WebAppInfo(
                    url="https://nu-questions-1.onrender.com"
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

    print("=== WEBAPP HANDLER TRIGGERED ===")

    if not update.message or not update.message.web_app_data:
        print("❌ Нет web_app_data")
        return

    print("📦 Получены данные:", update.message.web_app_data.data)

    try:
        data = json.loads(update.message.web_app_data.data)
    except Exception as e:
        print("❌ Ошибка JSON:", repr(e))
        return

    name = data.get("name", "Не указано")
    issue = data.get("issue", "Не указано")
    user_id = data.get("user_id", "Неизвестно")

    text = (
        "📩 Новый запрос\n\n"
        f"👤 Имя: {name}\n"
        f"📝 Вопрос:\n{issue}\n\n"
        f"🆔 ID пользователя: {user_id}"
    )

    try:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=text
        )
        print("✅ Сообщение отправлено в группу")
    except Exception as e:
        print("❌ Ошибка отправки в группу:", repr(e))
        return

    await update.message.reply_text("✅ Ваш запрос отправлен!")


# 🔹 СОЗДАНИЕ ПРИЛОЖЕНИЯ
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))

# 🔥 временно включаем debug
app.add_handler(MessageHandler(filters.ALL, debug))


# 🔹 ЗАПУСК ЧЕРЕЗ WEBHOOK
if __name__ == "__main__":
    print("🚀 Бот запущен через webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )
