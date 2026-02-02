import os
import asyncio
import requests
import re

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
POST_LIMIT = 30
DELAY = 5

fastapi_app = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ---------------- Background Queue ----------------
task_queue = asyncio.Queue()

async def background_worker():
    while True:
        keyword, context = await task_queue.get()
        pins = fetch_pinterest_pins(keyword)
        if not pins:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"❌ No images found for {keyword}")
        else:
            for pin in pins:
                try:
                    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"📌 #{keyword}\n{pin}")
                    await asyncio.sleep(DELAY)
                except Exception as e:
                    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"❌ Error posting: {e}")
                    break
        task_queue.task_done()

# ---------------- Pinterest Scraper ----------------
def fetch_pinterest_pins(keyword, limit=POST_LIMIT):
    url = f"https://r.jina.ai/https://www.pinterest.com/search/pins/?q={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("❌ Pinterest fetch error:", e)
        return []
    pins = list(set(re.findall(r"https://i\.pinimg\.com[^\"\\s]+", r.text)))
    return pins[:limit]

# ---------------- Telegram Command ----------------
async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /tag <keyword>\nExample: /tag mountain")
        return

    keyword = context.args[0]
    await update.message.reply_text(f"✅ Queued posting for: {keyword}")
    await task_queue.put((keyword, context))

telegram_app.add_handler(CommandHandler("tag", tag_command))

# ---------------- Startup ----------------
@fastapi_app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    await telegram_app.bot.delete_webhook(drop_pending_updates=True)
    await telegram_app.bot.set_webhook(f"https://tpost-szdp.onrender.com/{BOT_TOKEN}")
    print("✅ Telegram webhook registered")
    # Start background worker
    asyncio.create_task(background_worker())

# ---------------- Webhook ----------------
@fastapi_app.post(f"/{BOT_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        # Process update asynchronously, return immediately
        asyncio.create_task(telegram_app.process_update(update))
    except Exception as e:
        print("❌ Webhook error:", e)
    return {"ok": True}

# ---------------- Health check ----------------
@fastapi_app.get("/")
def health():
    return {"status": "Bot is running 🚀"}
