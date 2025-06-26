import asyncio
import feedparser
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from datetime import datetime, timedelta, timezone
import re
from html.parser import HTMLParser

TOKEN = "7302237060:AAH5af_frcbxsfv_HLLfp0wWZUlWpeomT7I"
CHAT_ID = "@UA_N_E_W_S"

bot = Bot(token=TOKEN)
dp = Dispatcher()

urls = [
    "https://www.unian.ua/rss",
    "https://www.pravda.com.ua/rss/view_news/",
    "https://rss.nv.ua/nv-news.rss",
    "https://www.bbc.com/ukrainian/rss.xml"
]

sent_articles = set()

def get_article_datetime(entry):
    if 'published_parsed' in entry:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

def is_fresh(published):
    return datetime.now(timezone.utc) - published < timedelta(hours=1)

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_html(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def extract_images(entry, max_photos=3):
    photos = []

    if "media_content" in entry:
        media = entry.media_content
        if isinstance(media, list):
            for m in media:
                url = m.get("url", "")
                if url and url not in photos:
                    photos.append(url)
                    if len(photos) >= max_photos:
                        return photos
        elif isinstance(media, dict):
            url = media.get("url", "")
            if url:
                photos.append(url)
                if len(photos) >= max_photos:
                    return photos

    if "enclosures" in entry:
        for enclosure in entry.enclosures:
            if enclosure.get("type", "").startswith("image"):
                url = enclosure.get("href", "")
                if url and url not in photos:
                    photos.append(url)
                    if len(photos) >= max_photos:
                        return photos

    summary = entry.get("summary", "")
    found_imgs = re.findall(r'<img[^>]+src="([^">]+)"', summary)
    for img_url in found_imgs:
        if img_url not in photos:
            photos.append(img_url)
            if len(photos) >= max_photos:
                return photos

    return photos

def get_full_text(entry):
    # Якщо є content, беремо його і очищаємо
    if 'content' in entry and len(entry.content) > 0:
        content = entry.content[0].value
        text = strip_html(content)
        # Обрізаємо, якщо занадто довгий
        return text[:1000] + ('...' if len(text) > 1000 else '')

    # Якщо немає content - беремо summary і очищаємо
    summary = entry.get("summary", "")
    text = strip_html(summary)
    return text[:1000] + ('...' if len(text) > 1000 else '')

def fetch_news():
    news = []
    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            published = get_article_datetime(entry)
            text = get_full_text(entry)
            photos = extract_images(entry)

            news.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": text,
                "photos": photos,
            })
    return news

async def check_news():
    news = fetch_news()
    for article in news:
        if article["title"] in sent_articles:
            continue
        if is_fresh(article["published"]):
            sent_articles.add(article["title"])

            # Формуємо текст у стилі новини з фото, додаємо емодзі і посилання
            caption = (
                f"📰 <b>{article['title']}</b>\n\n"
                f"{article['summary']}\n\n"
                f"🔗 <a href=\"{article['link']}\">Читати більше</a>"
            )

            if article["photos"]:
                if len(article["photos"]) == 1:
                    await bot.send_photo(chat_id=CHAT_ID, photo=article["photos"][0], caption=caption, parse_mode=ParseMode.HTML)
                else:
                    media = []
                    from aiogram.types import InputMediaPhoto
                    for i, photo_url in enumerate(article["photos"]):
                        if i == 0:
                            media.append(InputMediaPhoto(media=photo_url, caption=caption, parse_mode=ParseMode.HTML))
                        else:
                            media.append(InputMediaPhoto(media=photo_url))
                    await bot.send_media_group(chat_id=CHAT_ID, media=media)
            else:
                await bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode=ParseMode.HTML)

            print(f"Надіслано: {article['title']}")

            # Пауза між повідомленнями 60 секунд
            await asyncio.sleep(360)

async def main():
    print("Бот працює... Перевіряє новини кожні 5 хвилин.")
    while True:
        try:
            await check_news()
        except Exception as e:
            print(f"Помилка: {e}")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
