import os
import asyncio
import requests
import re
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import httpx  # for self-ping

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
POST_LIMIT = 30
DELAY = 5
SELF_PING_INTERVAL = 240  # seconds, ping every 4 minutes

# ---------------- FASTAPI + TELEGRAM ----------------
fastapi_app = FastAPI()
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ---------------- BACKGROUND QUEUE ----------------
task_queue = asyncio.Queue()

async def background_worker():
    while True:
        try:
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
        except Exception as e:
            print("❌ Background worker error:", e)
        finally:
            task_queue.task_done()

# ---------------- PINTEREST SCRAPER ----------------
def fetch_pinterest_pins(keyword, limit=POST_LIMIT):
    url = f"https://r.jina.ai/https://www.pinterest.com/search/pins/?q={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("❌ Pinterest fetch error:", e)
        return []
    pins = list(set(re.findall(r"https://i\.pinimg\.com[^\"\\s]+", r.text)))
    return pins[:limit]

# ---------------- TELEGRAM COMMAND ----------------
async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /tag <keyword>\nExample: /tag mountain")
        return

    keyword = context.args[0]
    await update.message.reply_text(f"✅ Queued posting for: {keyword}")
    await task_queue.put((keyword, context))

telegram_app.add_handler(CommandHandler("tag", tag_command))

# ---------------- STARTUP ----------------
@fastapi_app.on_event("startup")
async def startup_event():
    # Initialize bot
    await telegram_app.initialize()
    await telegram_app.bot.delete_webhook(drop_pending_updates=True)
    await telegram_app.bot.set_webhook(f"https://tpost-szdp.onrender.com/{BOT_TOKEN}")
    print("✅ Telegram webhook registered")

    # Start background Pinterest worker
    asyncio.create_task(background_worker())

    # Start self-ping task to keep free instance awake
    asyncio.create_task(self_ping())

# ---------------- SELF-PING ----------------
async def self_ping():
    url = "https://tpost-szdp.onrender.com/"
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.get(url)
                print("✅ Self-ping sent")
            except Exception as e:
                print("❌ Self-ping failed:", e)
            await asyncio.sleep(SELF_PING_INTERVAL)

# ---------------- TELEGRAM WEBHOOK ----------------
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

# ---------------- HEALTH CHECK ----------------
@fastapi_app.get("/")
def health():
    return {"status": "Bot is running 🚀"}
