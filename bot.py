import os
import json
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    MenuButtonWebApp,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://nu-questions-1.onrender.com"
GROUP_ID = -1003466972957 
PORT = int(os.environ.get("PORT", 10000))

# 1. Установка кнопки в меню (слева от ввода сообщения)
async def post_init(application):
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Задать вопрос",
            web_app=WebAppInfo(url=WEBHOOK_URL)
        )
    )
    logger.info("✅ Кнопка меню успешно настроена")

# 2. Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    # Дублируем кнопку в самой клавиатуре для удобства
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton(text="📨 Открыть форму", web_app=WebAppInfo(url=WEBHOOK_URL))]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Нажми на кнопку <b>Открыть форму</b> ниже или используй синюю кнопку в меню, чтобы отправить свой вопрос.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# 3. Обработка данных из WebApp
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.web_app_data:
        return

    try:
        # Парсим данные, которые прислал JS из WebApp
        raw_data = update.message.web_app_data.data
        data = json.loads(raw_data)
        
        name = data.get("name", "Не указано")
        issue = data.get("issue", "Текст отсутствует")
        
        # Данные пользователя берем напрямую из Telegram
        user = update.effective_user
        username = f"@{user.username}" if user.username else "скрыт"
        user_id = user.id

        text_to_group = (
            f"📩 <b>Новый запрос</b>\n\n"
            f"👤 <b>Имя:</b> {name}\n"
            f"🔗 <b>Аккаунт:</b> {username}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            f"📝 <b>Вопрос:</b>\n{issue}"
        )

        # Отправка в группу
        await context.bot.send_message(
            chat_id=GROUP_ID, 
            text=text_to_group, 
            parse_mode="HTML"
        )
        
        # Ответ пользователю
        await update.message.reply_text("✅ Твой запрос отправлен! Мы скоро изучим его.")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке WebApp: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке формы.")

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))

    print(f"🚀 Запуск webhook на порту {PORT}...")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )
