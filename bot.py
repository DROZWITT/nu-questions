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

# Настройка логирования для Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не установлен!")

PORT = int(os.environ.get("PORT", 10000))

# URL вашего приложения на Render
WEBHOOK_URL = "https://nu-questions-1.onrender.com"

# ID вашей группы (убедитесь, что бот добавлен в группу как администратор)
GROUP_ID = -1003466972957


# 🔹 DEBUG: Получение ID чата (напишите любое сообщение в группе, чтобы увидеть ID)
async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"DEBUG: Message from chat_id: {update.effective_chat.id}")


# 🔹 КОМАНДА /START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Работаем только в личке с пользователем
    if update.effective_chat.type != "private":
        return

    # ВАЖНО: Используем KeyboardButton для работы tg.sendData()
    keyboard = ReplyKeyboardMarkup([
        [
            KeyboardButton(
                text="📨 Открыть форму запроса",
                web_app=WebAppInfo(url=WEBHOOK_URL)
            )
        ]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "Нажмите кнопку на клавиатуре, чтобы заполнить форму:",
        reply_markup=keyboard,
    )


# 🔹 ОБРАБОТКА ДАННЫХ ИЗ WEBAPP
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("=== ПОЛУЧЕНЫ ДАННЫЕ ИЗ WEBAPP ===")
    
    # Проверка наличия данных
    if not update.message.web_app_data:
        print("❌ Данные web_app_data отсутствуют")
        return

    raw_data = update.message.web_app_data.data
    print(f"📦 Сырые данные: {raw_data}")

    try:
        data = json.loads(raw_data)
    except Exception as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return

    name = data.get("name", "Не указано")
    issue = data.get("issue", "Не указано")
    user_id = data.get("user_id", "Неизвестно")
    username = update.effective_user.username or "нет юзернейма"

    # Формируем текст для группы
    text_to_group = (
        "📩 **Новый запрос из WebApp**\n\n"
        f"👤 **Имя:** {name}\n"
        f"🔗 **Аккаунт:** @{username}\n"
        f"🆔 **ID:** `{user_id}`\n\n"
        f"📝 **Вопрос:**\n{issue}"
    )

    try:
        # Отправка в группу
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=text_to_group,
            parse_mode="Markdown"
        )
        print("✅ Сообщение успешно отправлено в группу")
        
        # Подтверждение пользователю
        await update.message.reply_text("✅ Ваш запрос успешно отправлен в поддержку!")
        
    except Exception as e:
        print(f"❌ Ошибка при отправке в группу: {e}")
        await update.message.reply_text("❌ Произошла ошибка при отправке. Попробуйте позже.")


# 🔹 ЗАПУСК
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Хендлеры
    app.add_handler(CommandHandler("start", start))
    # Этот фильтр ловит данные из WebApp
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))
    # Вспомогательный хендлер для отладки
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, debug))

    print(f"🚀 Бот запускается на порту {PORT}...")
    
    # Запуск Webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )
