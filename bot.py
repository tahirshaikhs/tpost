import os
import asyncio
import requests
import re

from fastapi import FastAPI, Request
import uvicorn

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ---------------- Config ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))

POST_LIMIT = 30
DELAY = 5

# ---------------- Pinterest Scraper ----------------
def fetch_pinterest_pins(keyword, limit=POST_LIMIT):
    url = f"https://r.jina.ai/https://www.pinterest.com/search/pins/?q={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching Pinterest images: {e}")
        return []

    text = response.text
    pins = list(set(re.findall(r"https://i\.pinimg\.com[^\"\\s]+", text)))
    return pins[:limit]

# ---------------- Telegram Command ----------------
async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage:\n/tag <keyword>\nExample: /tag mountain"
        )
        return

    keyword = context.args[0]

    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"✅ Bot connected.\nStarting URL posting for: #{keyword}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Cannot post to channel:\n{e}")
        return

    await update.message.reply_text(f"🔍 Fetching Pinterest URLs for: {keyword}")
    pins = fetch_pinterest_pins(keyword)

    if not pins:
        await update.message.reply_text("❌ No Pinterest images found.")
        return

    for pin_url in pins:
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"📌 #{keyword}\n{pin_url}"
            )
            await asyncio.sleep(DELAY)
        except Exception as e:
            await update.message.reply_text(f"❌ Error posting URL:\n{e}")
            break

# ---------------- FastAPI App ----------------
fastapi_app = FastAPI()

bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
bot_app.add_handler(CommandHandler("tag", tag_command))

# ---------------- Startup Event ----------------
@fastapi_app.on_event("startup")
async def on_startup():
    WEBHOOK_URL = f"https://tpost-szdp.onrender.com/{BOT_TOKEN}"

    await bot_app.initialize()
    await bot_app.bot.delete_webhook()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    await bot_app.start()

    print("✅ Webhook set:", WEBHOOK_URL)

# ---------------- Webhook Endpoint ----------------
@fastapi_app.post(f"/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.update_queue.put(update)
    return {"ok": True}

# ---------------- Health Check ----------------
@fastapi_app.get("/")
def index():
    return {"status": "Bot is running 🚀"}

# ---------------- Uvicorn Runner ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:fastapi_app",  # 👈 change "main" if filename is different
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
