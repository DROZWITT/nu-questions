import os
import re
import logging
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# --- Настройки ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не установлен!")

GROUP_ID = -1003466972957
CATALOG_THREAD_ID = 8  # Ваша тема для каталога
MEMORY_FILE = "posted_links.txt" # Файл памяти

# --- Функции памяти ---
def load_posted_links():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def save_posted_link(url):
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}\n")

# --- Основная функция парсинга ---
async def scan_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Проверяю все позиции на сайте. Сверяю с базой...")

    try:
        url = "https://ligo-records.info/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        posted_links = load_posted_links()
        
        new_items = []

        # Ищем все контейнеры постов
        for post in soup.find_all('div', class_='item--announce'):
            link_tag = post.find('a')
            if not link_tag:
                continue
                
            href = link_tag.get('href', '')
            
            # ❗️ Пропускаем объявления
            if '/adds/' in href:
                continue
                
            # ❗️ Проверяем память
            if href in posted_links:
                continue
                
            # Сохраняем найденную НОВУЮ позицию в список
            new_items.append((post, href))

        if not new_items:
            await update.message.reply_text("🤷‍♂️ Новых игр или фильмов пока нет. Все позиции проверены, дубликаты пропущены!")
            return

        # Разворачиваем список (публикуем от старых к новым)
        new_items.reverse()
        
        # Публикуем максимум 3 новинки за один раз
        items_to_post = new_items[:3]
        await update.message.reply_text(f"🔥 Найдено новых позиций: {len(new_items)}. Публикую {len(items_to_post)} из них...")

        for target_post, post_url in items_to_post:
            # 1. Вытаскиваем картинку и название
            img_tag = target_post.find('img')
            title = img_tag.get('alt', 'Без названия') if img_tag else "Без названия"

            image_url = None
            if img_tag:
                image_url = img_tag.get('data-src') or img_tag.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = 'https://ligo-records.info' + image_url

            # 2. Проваливаемся внутрь поста за полным текстом
            description = "Описание отсутствует."
            full_url = 'https://ligo-records.info' + post_url if post_url.startswith('/') else post_url
                
            try:
                full_resp = requests.get(full_url, headers=headers)
                full_soup = BeautifulSoup(full_resp.text, 'html.parser')
                text_block = full_soup.find('div', class_=re.compile(r'(item__text|full-text|item__desc)'))
                
                if text_block:
                    # ❗️ ИСПРАВЛЕНИЕ ТЕКСТА: заменяем HTML-теги на реальные переносы строк
                    description = text_block.get_text(separator='\n', strip=True)
                    
                    if len(description) > 850:
                        description = description[:850] + "...\n\n(Полная версия на сайте)"
            except Exception as e:
                logging.error(f"Не удалось получить внутреннюю страницу: {e}")

            tags = "#LigoRecords #Каталог #Новинка"

            # 3. Ищем официальный трейлер на YouTube
            platform = ""
            url_lower = post_url.lower()
            if "ps5" in url_lower: platform = "PS5"
            elif "ps4" in url_lower: platform = "PS4"
            elif "xbox" in url_lower: platform = "Xbox"
            elif "pc" in url_lower or "windows" in url_lower: platform = "PC"

            search_query = f"{title} {platform} official trailer".strip()
            query = urllib.parse.urlencode({"search_query": search_query})
            yt_search_url = f"https://www.youtube.com/results?{query}"
            
            yt_response = requests.get(yt_search_url, headers=headers)
            video_ids = re.findall(r"watch\?v=(\S{11})", yt_response.text)
            youtube_link = f"https://www.youtube.com/watch?v={video_ids[0]}" if video_ids else None

            # 4. Отправляем в Telegram
            message_1_text = f"<b>{title}</b>\n\n{description}\n\n{tags}"
            
            if image_url:
                await context.bot.send_photo(
                    chat_id=GROUP_ID, photo=image_url, caption=message_1_text,
                    parse_mode='HTML', message_thread_id=CATALOG_THREAD_ID
                )
            else:
                await context.bot.send_message(
                    chat_id=GROUP_ID, text=message_1_text,
                    parse_mode='HTML', message_thread_id=CATALOG_THREAD_ID
                )

            # ❗️ КРАСИВОЕ ОФОРМЛЕНИЕ YOUTUBE С ПОДСКАЗКОЙ
            if youtube_link:
                youtube_msg = (
                    f"📺 <a href='{youtube_link}'><b>Смотреть трейлер: {title}</b></a>\n"
                    f"<i>(Нажмите на картинку плеера ниже, чтобы смотреть прямо в Telegram)</i>"
                )
                await context.bot.send_message(
                    chat_id=GROUP_ID, text=youtube_msg,
                    parse_mode='HTML', message_thread_id=CATALOG_THREAD_ID
                )

            # ❗️ УСПЕШНО ОПУБЛИКОВАЛИ - ЗАПИСЫВАЕМ В ПАМЯТЬ
            save_posted_link(post_url)

        await update.message.reply_text("✅ Выбранные позиции успешно опубликованы и записаны в базу!")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка: {e}")

# --- Команда очистки памяти ---
async def clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    open(MEMORY_FILE, 'w').close() 
    await update.message.reply_text("🧹 Память успешно очищена! При следующем запуске /scan бот опубликует все игры заново.")

# --- Фейковый сервер для Render ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Catalog Parser is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

# --- Запуск ---
if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("scan", scan_catalog))
    app.add_handler(CommandHandler("clearcache", clear_cache))
    
    print("🚀 Бот-парсер запущен...")
    app.run_polling()
