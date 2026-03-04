# ЗАМЕНИТЕ ЭТО ЧИСЛО на то, которое получите в шаге 1
QUESTIONS_TOPIC_ID = 12345 

async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.web_app_data:
        return

    try:
        data = json.loads(update.message.web_app_data.data)
        name = data.get("name", "Не указано")
        issue = data.get("issue", "Пусто")
        user = update.effective_user
        username = f"@{user.username}" if user.username else "нет юзернейма"

        text_to_group = (
            f"📩 <b>Новый запрос</b>\n\n"
            f"👤 <b>Имя:</b> {name}\n"
            f"🔗 <b>Аккаунт:</b> {username}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
            f"📝 <b>Вопрос:</b>\n{issue}"
        )

        # ВАЖНО: Добавляем message_thread_id
        await context.bot.send_message(
            chat_id=GROUP_ID, 
            message_thread_id=QUESTIONS_TOPIC_ID, # Вот этот параметр решает проблему
            text=text_to_group, 
            parse_mode="HTML"
        )
        
        await update.message.reply_text("✅ Запрос отправлен в тему 'Вопросы'!")
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка при отправке.")
