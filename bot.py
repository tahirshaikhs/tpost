import os
import requests
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from fastapi import FastAPI, Request
import uvicorn

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Set in Render Environment
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))  # numeric channel ID
POST_LIMIT = 30
DELAY = 5

def fetch_pinterest_pins(keyword, limit=POST_LIMIT):
    url = f"https://r.jina.ai/https://www.pinterest.com/search/pins/?q={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching Pinterest images: {e}")
        return []
    text = response.text
    pins = list(set(re.findall(r"https://i\.pinimg\.com[^\"\\s]+", text)))
    return pins[:limit]

async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage:\n/tag <keyword>\nExample: /tag mountain")
        return
    keyword = context.args[0]

    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"✅ Bot connected. Starting URL posting for: {keyword}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Cannot post to channel:\n{e}")
        return

    await update.message.reply_text(f"🔍 Fetching Pinterest URLs for: {keyword}")
    pins = fetch_pinterest_pins(keyword)
    if not pins:
        await update.message.reply_text("❌ No Pinterest images found. Try another keyword.")
        return

    for pin_url in pins:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"📌 #{keyword}\n{pin_url}")
            await update.message.reply_text(f"📌 Posted URL:\n{pin_url}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error posting URL:\n{e}")
            break

# ------------------ FastAPI + Webhook ------------------
app = FastAPI()
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
bot_app.add_handler(CommandHandler("tag", tag_command))

@app.post(f"/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.update_queue.put(update)
    return {"ok": True}

@app.get("/")
def index():
    return {"status": "Bot is running"}

if __name__ == "__main__":
    # Replace with your public URL on Render + BOT_TOKEN
    WEBHOOK_URL = f"https://your-app-name.onrender.com/{BOT_TOKEN}"
    bot_app.bot.set_webhook(WEBHOOK_URL)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
