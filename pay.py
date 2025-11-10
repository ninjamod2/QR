import os
import re
import json
import logging
import asyncio
import subprocess
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights, User

# Telegram API credentials
API_ID = 22627280
API_HASH = "b2e5eb5e3dd886f5b8be6a749a26f619"
OWNER_ID = 1240179115  # Your Telegram ID

# Configuration
client = TelegramClient('session_name', API_ID, API_HASH)
channel_link = "https://t.me/+GUUGE6jYNKZiZDll"
price_list_link = "https://t.me/VIPCHEATS_FEESBACK/1221"
upload_qr_code = 'QR.jpg'
gif_path = 'hello.gif'
upi_id = "ninjagamerop0786@ybl"
cooldown_period = 600  # 10 minutes
last_qr_request = {}
free_requests = {}  # For tracking 'free' spam

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache messages
cached_messages = {
    "qr": f"**Here is my QR code for payment.**\n\n💳 UPI ID: `{upi_id}`\n\n📣 Join our channel: {channel_link}\n\n📸 **Please Send a Screenshot of Payment**",
    "hi": "👋 Hello! How can I assist you?",
    "free": f"🖕🏻 **FREE VALA CHANNEL PER MILEGA!** 🖕🏻\n\n🎯 [**CLICK HERE**]({channel_link})",
    "cooldown": "🖕🏻 **BSDK RUK JA 10 Min USKE BAAD MILEGA QR.** 🖕🏻",
    "mute_warning": "❌ **Spam Detected! You're muted for 5 minutes.**"
}

# SMS Reading (via Termux)
def get_latest_sms():
    try:
        result = subprocess.run(["termux-sms-list"], capture_output=True, text=True)
        sms_list = json.loads(result.stdout)
        if sms_list:
            return sms_list[0]
    except Exception as e:
        logger.error(f"Error reading SMS: {e}")
    return None

# Extract payment details
def extract_payment_details(sms_body):
    upi_pattern = r"(?i)(?:received|credited)\s+\u20b9?(\d+(\.\d{1,2})?)\s+from\s+([a-zA-Z\s]+)"
    match = re.search(upi_pattern, sms_body)
    if match:
        amount = match.group(1)
        sender = match.group(3).strip()
        return amount, sender
    return None, None

# Background SMS checker
async def check_sms():
    last_checked = None
    while True:
        sms = get_latest_sms()
        if sms and sms['body'] != last_checked:
            last_checked = sms['body']
            amount, sender = extract_payment_details(sms['body'])
            if amount and sender:
                message = f"✅ **Payment Received!**\n💰 **Amount:** ₹{amount}\n👤 **Sender:** {sender}"
                # Only notify OWNER privately
                await client.send_message(OWNER_ID, message)
        await asyncio.sleep(30)

# Main Handler
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        # Skip any non-private chat (group, channel, bot)
        chat = await event.get_chat()
        if not isinstance(chat, User):
            return  # Ignore groups/channels
        if chat.bot:
            return  # Ignore bots

        user_id = event.sender_id
        message_text = event.raw_text.lower().strip()
        now = datetime.now()

        # QR / UPI Request
        if message_text in ['qr', 'upi', 'scanner', 'scaner', 'scnr']:
            if user_id in last_qr_request and (now - last_qr_request[user_id]).total_seconds() < cooldown_period:
                await event.reply(cached_messages["cooldown"])
                return
            await client.send_file(
                event.chat_id,
                upload_qr_code,
                caption=cached_messages["qr"],
                link_preview=False
            )
            last_qr_request[user_id] = now
            asyncio.create_task(check_sms())

        # Price Command
        elif 'price' in message_text:
            await event.reply(f"🛒 **Here is our price list:** {price_list_link}", link_preview=False)

        # Help
        elif 'help' in message_text:
            help_message = f"""
🤖 **Available Commands:**

- **`qr`** → Get QR Code + UPI ID together  
- **`price`** → Get the price list link  
- **`/id`** → Get your own Telegram ID  
- **`/id @username`** (Owner Only) → Get user ID of a specific user  
- **`free`** → Get a response with a channel link  
"""
            await event.reply(help_message)

        # ID Commands
        elif message_text.startswith('/id'):
            parts = message_text.split()
            if len(parts) == 1:
                await event.reply(f"**Your Telegram ID:** `{user_id}`")
            elif len(parts) > 1 and user_id == OWNER_ID:
                try:
                    username = parts[1]
                    entity = await client.get_entity(username)
                    if isinstance(entity, User):
                        await event.reply(f"**User ID of {username}:** `{entity.id}`")
                    else:
                        await event.reply("❌ **That’s not a user account.**")
                except Exception as e:
                    await event.reply("❌ **User not found!**")
                    logger.error(f"Error fetching user ID: {e}")
            else:
                await event.reply("❌ **You are not authorized to check other users' IDs!**")

        # /unmute @username (Owner Only)
        elif message_text.startswith("/unmute") and user_id == OWNER_ID:
            parts = message_text.split()
            if len(parts) == 2:
                try:
                    target_user = parts[1]
                    entity = await client.get_entity(target_user)
                    if isinstance(entity, User) and not entity.bot:
                        await client(EditBannedRequest(
                            peer=event.chat_id,
                            user_id=entity.id,
                            banned_rights=ChatBannedRights(
                                until_date=None,
                                send_messages=False
                            )
                        ))
                        await event.reply(f"✅ **User {target_user} has been unmuted.**")
                    else:
                        await event.reply("❌ **Cannot unmute bot or channel.**")
                except Exception as e:
                    await event.reply("❌ **Failed to unmute user.**")
                    logger.error(f"Unmute error: {e}")
            else:
                await event.reply("❌ **Usage:** `/unmute @username`")

        # Hi / Hello / Greetings
        elif message_text in ['hi', 'hello', 'hey', 'hii', 'hlw']:
            await client.send_file(event.chat_id, gif_path, caption=cached_messages["hi"])

        # Free Command - With Mute Logic and Auto Delete
        elif 'free' in message_text:
            user_times = free_requests.get(user_id, [])
            user_times = [t for t in user_times if now - t < timedelta(minutes=5)]
            user_times.append(now)
            free_requests[user_id] = user_times

            if len(user_times) > 5:
                await event.reply(cached_messages["mute_warning"])
                try:
                    await client(EditBannedRequest(
                        peer=event.chat_id,
                        user_id=user_id,
                        banned_rights=ChatBannedRights(
                            until_date=now + timedelta(minutes=5),
                            send_messages=True
                        )
                    ))
                except Exception as e:
                    logger.error(f"Failed to mute user: {e}")
            else:
                msg = await event.reply(cached_messages["free"], link_preview=False)
                await asyncio.sleep(60)
                try:
                    await msg.delete()
                except Exception as e:
                    logger.error(f"Failed to delete free message: {e}")

    except Exception as e:
        logger.error(f"Error in handler: {e}")

# Start Bot
client.start()
logger.info("🤖 Payment Bot is running... (Private users only, safe mode)")
client.run_until_disconnected()
