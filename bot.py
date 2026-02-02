import os
import asyncio
import requests
import re

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
POST_LIMIT = 30
DELAY = 5

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

# ---------------- MAIN ----------------
async def main():
    # Build bot application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("tag", tag_command))

    # Start background worker
    asyncio.create_task(background_worker())

    # Start polling (no webhook needed)
    print("✅ Bot started with long polling")
    await application.run_polling()

# ---------------- ENTRY POINT ----------------
if __name__ == "__main__":
    asyncio.run(main())
