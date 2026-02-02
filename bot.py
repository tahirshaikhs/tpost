import os
import requests
import re

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
POST_LIMIT = 30
DELAY = 5

# FastAPI app
app = FastAPI()
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ---------------- Pinterest Scraper ----------------
def fetch_pinterest_pins(keyword, limit=POST_LIMIT):
    url = f"https://r.jina.ai/https://www.pinterest.com/search/pins/?q={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("Pinterest error:", e)
        return []
    pins = list(set(re.findall(r"https://i\.pinimg\.com[^\"\\s]+", r.text)))
    return pins[:limit]

# ---------------- Telegram Command ----------------
async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /tag <keyword>")
        return

    keyword = context.args[0]
    await update.message.reply_text(f"🔍 Fetching Pinterest URLs for: {keyword}")
    pins = fetch_pinterest_pins(keyword)
    if not pins:
        await update.message.reply_text("❌ No images found.")
        return

    for pin in pins:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"📌 #{keyword}\n{pin}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error posting: {e}")
            break

# Add command handler
bot_app.add_handler(CommandHandler("tag", tag_command))

# ---------------- Startup: set webhook ----------------
@app.on_event("startup")
async def startup_event():
    await bot_app.initialize()
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    await bot_app.bot.set_webhook(f"https://tpost-szdp.onrender.com/{BOT_TOKEN}")
    print("✅ Webhook set successfully")

# ---------------- Webhook endpoint ----------------
@app.post(f"/{BOT_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as e:
        print("Webhook error:", e)
    return {"ok": True}

# ---------------- Health check ----------------
@app.get("/")
def health():
    return {"status": "Bot is running"}
