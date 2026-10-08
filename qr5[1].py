import io
import logging
import asyncio
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

SESSION_NAME = os.getenv("TG_SESSION", "session_name")

# ✅ TWO QR FILES
upload_qr_code1 = os.getenv("QR_FILE_1", "qr1.jpg")
upload_qr_code2 = os.getenv("QR_FILE_2", "qr2.jpg")

# ✅ TWO UPI IDs
upi_id1 = os.getenv("UPI_ID_1", "")
upi_id2 = os.getenv("UPI_ID_2", "")

cooldown_period = int(os.getenv("COOLDOWN_SECONDS", "600"))
price_list_link = os.getenv("PRICE_LIST_LINK", "")

channel_links = [
    os.getenv("CHANNEL_LINK_1", ""),
    os.getenv("CHANNEL_LINK_2", ""),
]
channel_links = [c for c in channel_links if c]

if not API_ID or not API_HASH or not OWNER_ID:
    raise SystemExit("❌ Missing API_ID / API_HASH / OWNER_ID in .env")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

formatted_links = "\n".join(
    [f"➡️ [JOIN CHANNEL {i+1}]({link})" for i, link in enumerate(channel_links)]
)

# ================= STATE =================
last_qr_request = {}
request_tracker = {}
warning_tracker = {}

# ================= DAILY STATS =================
today_date = datetime.now().date()
daily_stats = {"qr": 0, "screenshot": 0, "free": 0}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= UPI TEXT BUILD =================
upi_text = ""
if upi_id1:
    upi_text += f"💳 UPI ID 1: `{upi_id1}`\n"
if upi_id2:
    upi_text += f"💳 UPI ID 2: `{upi_id2}`\n"

QR_MESSAGE = f"""**Choose any QR to pay**

{upi_text}
📢 Join Channel:
{formatted_links}

📸 Send payment screenshot within 10 minutes
"""

FREE_MESSAGE = f"""भाई कब तक FREE वाला खेलेगा ? 😏  
FREE वाला चैनल पर मिलेगा 👇

{formatted_links}
"""

# ================= LOAD QR =================
try:
    with open(upload_qr_code1, "rb") as f:
        qr_bytes1 = f.read()

    with open(upload_qr_code2, "rb") as f:
        qr_bytes2 = f.read()

except FileNotFoundError as e:
    raise SystemExit(f"❌ QR file not found: {e}")


def _norm(txt: str) -> str:
    return (txt or "").lower().strip()


def _is_image_doc(event) -> bool:
    f = getattr(event.message, "file", None)
    if not f:
        return False
    mt = getattr(f, "mime_type", None)
    return bool(mt and mt.startswith("image/"))


async def _delete_later(msg, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


# ================= MAIN HANDLER =================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    global today_date, daily_stats

    try:
        if not event.is_private:
            return

        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return

        user_id = event.sender_id
        text = _norm(event.raw_text)
        now = datetime.now()

        # ===== Daily reset =====
        if now.date() != today_date:
            today_date = now.date()
            daily_stats = {"qr": 0, "screenshot": 0, "free": 0}

        # ===== Owner stats =====
        if text == "/stats" and user_id == OWNER_ID:
            await event.reply(
                "📊 Today Report\n\n"
                f"QR Requests: {daily_stats['qr']}\n"
                f"Screenshots Received: {daily_stats['screenshot']}\n"
                f"Free Requests: {daily_stats['free']}\n"
            )
            return

        # ===== Global Limit =====
        tracked_keywords = [
            "qr", "upi", "scan", "scanner", "qrcode",
            "payment", "pay", "barcode",
            "free", "price"
        ]

        if any(word in text for word in tracked_keywords):

            user_times = request_tracker.get(user_id, [])
            user_times = [t for t in user_times if now - t < timedelta(minutes=10)]

            if len(user_times) >= 5:
                warn_msg = await event.reply("⚠️ Please stop spamming requests.")
                asyncio.create_task(_delete_later(warn_msg, cooldown_period))
                return

            user_times.append(now)
            request_tracker[user_id] = user_times

        # ===== QR =====
        qr_keywords = ["qr", "upi", "scan", "scanner", "qrcode", "payment", "pay", "barcode"]

        if any(word in text for word in qr_keywords):

            if user_id in last_qr_request:
                diff = (now - last_qr_request[user_id]).total_seconds()
                if diff < cooldown_period:
                    await event.reply("⏳ Please wait before requesting QR again.")
                    return

            daily_stats["qr"] += 1

            qr_file1 = io.BytesIO(qr_bytes1)
            qr_file1.name = upload_qr_code1

            qr_file2 = io.BytesIO(qr_bytes2)
            qr_file2.name = upload_qr_code2

            sent = await client.send_file(
                event.chat_id,
                [qr_file1, qr_file2],  # ✅ TWO QR
                caption=QR_MESSAGE,
                parse_mode="md"
            )

            last_qr_request[user_id] = now

            async def delete_qr():
                await asyncio.sleep(cooldown_period)
                try:
                    await sent.delete()
                except Exception:
                    pass
                last_qr_request.pop(user_id, None)

            asyncio.create_task(delete_qr())
            return

        # ===== Screenshot =====
        if event.photo or _is_image_doc(event):

            if user_id not in last_qr_request:
                return

            diff = (now - last_qr_request[user_id]).total_seconds()
            if diff > cooldown_period:
                last_qr_request.pop(user_id, None)
                return

            daily_stats["screenshot"] += 1

            await event.reply(
                "✅ Payment Screenshot Received ✅ !\n\n⏳ Please wait while we verify."
            )

            sender = await event.get_sender()
            username = getattr(sender, "username", None)
            first_name = getattr(sender, "first_name", "") or ""
            last_name = getattr(sender, "last_name", "") or ""
            user_display = f"@{username}" if username else f"{first_name} {last_name}".strip()

            await client.forward_messages(OWNER_ID, event.message, from_peer=event.chat_id)

            await client.send_message(
                OWNER_ID,
                "📩 Payment Screenshot\n\n"
                f"👤 User: {user_display}\n"
                f"🆔 ID: {user_id}\n"
                f"🕒 Time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            last_qr_request.pop(user_id, None)
            return

        # ===== PRICE =====
        if "price" in text:
            msg1 = await event.reply(f"🛒 Price List:\n{price_list_link}")
            msg2 = await event.reply("कितने दिन का लेना है?")
            asyncio.create_task(_delete_later(msg1, cooldown_period))
            asyncio.create_task(_delete_later(msg2, cooldown_period))
            return

        # ===== FREE =====
        if "free" in text:
            daily_stats["free"] += 1
            msg = await event.reply(FREE_MESSAGE, parse_mode="md")
            asyncio.create_task(_delete_later(msg, cooldown_period))
            return

        # ===== CHANNEL =====
        if "channel" in text or "link" in text:
            await event.reply(
                f"📢 Join Our Channels:\n\n{formatted_links}",
                parse_mode="md"
            )
            return

    except Exception as e:
        logger.exception(f"Error: {e}")


client.start()
print("🤖 Bot running with 2 QR + 2 UPI system...")
client.run_until_disconnected()