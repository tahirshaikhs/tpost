import os
import asyncio
import requests
import re

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ================== CONFIG ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))

POST_LIMIT = 30
DELAY = 5  # seconds between posts

# ================== GLOBAL QUEUE ==================
task_queue = asyncio.Queue()

# ================== PINTEREST SCRAPER ==================
def fetch_pinterest_pins(keyword, limit=POST_LIMIT):
    url = f"https://r.jina.ai/https://www.pinterest.com/search/pins/?q={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("❌ Pinterest fetch error:", e)
        return []

    pins = list(
        set(re.findall(r"https://i\.pinimg\.com[^\"\\s]+", r.text))
    )
    return pins[:limit]

# ================== BACKGROUND WORKER ==================
async def background_worker(application):
    while True:
        keyword, chat_id = await task_queue.get()

        try:
            pins = fetch_pinterest_pins(keyword)

            if not pins:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ No images found for {keyword}"
                )
            else:
                for pin in pins:
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=f"📌 #{keyword}\n{pin}"
                    )
                    await asyncio.sleep(DELAY)

        except Exception as e:
            print("❌ Background worker error:", e)

        finally:
            task_queue.task_done()

# ================== COMMAND ==================
async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /tag <keyword>\nExample: /tag mountain"
        )
        return

    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id

    await update.message.reply_text(
        f"✅ Queued posting for: {keyword}"
    )

    await task_queue.put((keyword, chat_id))

# ================== POST INIT ==================
async def post_init(application):
    application.create_task(background_worker(application))

# ================== MAIN ==================
def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        raise RuntimeError("❌ BOT_TOKEN or CHANNEL_ID missing")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("tag", tag_command))
    application.post_init = post_init

    print("✅ Bot started with long polling")
    application.run_polling()

# ================== ENTRY POINT ==================
if __name__ == "__main__":
    main()
