import telebot
import qrcode
import re
import time
from PIL import Image, ImageDraw

# --------------- CONFIG ----------------

BOT_TOKEN = "8432347309:AAGXxQVW1YcvlRaHns-xNzn_mGE4wllQ55A"
UPI_VPA = "sksodha207@okicici"
PAYEE_NAME = "SHADOW"

# Admin Telegram numeric IDs (no quotes)
ADMIN_IDS = {6799525497}

bot = telebot.TeleBot(BOT_TOKEN)

# In-memory order DB
orders = {}   # order_id : {amount, user, status}


# --------------- PREMIUM QR CARD DESIGN ----------------

def make_qr(amount, order_id):

    upi_link = (
        f"upi://pay?pa={UPI_VPA}"
        f"&pn={PAYEE_NAME}"
        f"&am={amount}"
        f"&cu=INR"
        f"&tn=Escrow%20Order%20{order_id}"
    )

    qr = qrcode.QRCode(box_size=12, border=2)
    qr.add_data(upi_link)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Background canvas
    bg = Image.new("RGB", (780, 1000), "#e9ecef")

    # Card layer
    card = Image.new("RGB", (700, 900), "white")
    draw = ImageDraw.Draw(card)

    # Golden Header
    draw.rounded_rectangle((0, 0, 700, 120), 40, fill="#d4af37")
    draw.text((240, 45), "ESCROW PAYMENT", fill="black")

    # Amount Tag
    draw.rounded_rectangle((250, 140, 450, 200), 25, fill="#111111")
    draw.text((320, 155), f"₹{amount}", fill="white")

    # Order ID
    draw.text((250, 230), f"Order ID : {order_id}", fill="black")

    # QR Code
    card.paste(qr_img.resize((520, 520)), (90, 270))

    # Footer UPI Strip
    draw.rounded_rectangle((140, 820, 560, 870), 25, fill="#222222")
    draw.text((210, 835), f"UPI  {UPI_VPA}", fill="white")

    # Paste card to bg
    bg.paste(card, (40, 50))

    filename = f"qr_{order_id}.png"
    bg.save(filename)

    return filename


# --------------- GROUP QR COMMAND ----------------

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.text)
def create_qr(message):

    text = message.text.upper().replace(" ", "")

    match = re.findall(r"^QR(\d+)$", text)
    if not match:
        return

    amount = match[0]
    order_id = int(time.time())

    # store order
    orders[order_id] = {
        "amount": amount,
        "user": message.from_user.id,
        "status": "PENDING"
    }

    file = make_qr(amount, order_id)

    caption = (
        f"🟡 Google Pay Compatible QR\n"
        f"💰 Amount: ₹{amount}\n"
        f"🧾 Order ID: {order_id}\n"
        f"📌 Status: PENDING (Awaiting Payment)\n\n"
        f"Scan & Pay — Amount Auto-Filled"
    )

    with open(file, "rb") as img:
        bot.send_photo(message.chat.id, img, caption=caption)


# --------------- ESCROW ADMIN UTILS ----------------

def is_admin(uid):
    return uid in ADMIN_IDS


# --------------- HOLD ----------------

@bot.message_handler(commands=["hold"])
def esc_hold(message):

    bot.reply_to(message, f"⌛ Processing HOLD — Your ID: {message.from_user.id}")

    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Not Authorized (Admin ID mismatch)")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /hold <order_id>")
        return

    order_id = int(parts[1])

    if order_id not in orders:
        bot.reply_to(message, "❌ Order Not Found")
        return

    orders[order_id]["status"] = "HOLD"

    bot.reply_to(
        message,
        f"🟡 ORDER MOVED TO HOLD\n\n"
        f"🧾 Order: {order_id}\n"
        f"Funds locked in escrow."
    )


# --------------- RELEASE ----------------

@bot.message_handler(commands=["release"])
def esc_release(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Not Authorized")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /release <order_id>")
        return

    order_id = int(parts[1])

    if order_id not in orders:
        bot.reply_to(message, "❌ Order Not Found")
        return

    orders[order_id]["status"] = "RELEASED"

    bot.reply_to(
        message,
        f"🟢 ORDER RELEASED\n\n"
        f"🧾 Order: {order_id}\n"
        f"💸 Funds paid to seller\n"
        f"✔ Escrow Completed"
    )


# --------------- CANCEL ----------------

@bot.message_handler(commands=["cancel"])
def esc_cancel(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Not Authorized")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /cancel <order_id>")
        return

    order_id = int(parts[1])

    if order_id not in orders:
        bot.reply_to(message, "❌ Order Not Found")
        return

    orders[order_id]["status"] = "CANCELLED"

    bot.reply_to(
        message,
        f"🔴 ORDER CANCELLED\n\n"
        f"🧾 Order: {order_id}\n"
        f"↩ Refund to buyer initiated"
    )


# --------------- ORDERS PANEL ----------------

@bot.message_handler(commands=["orders"])
def esc_orders(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Not Authorized")
        return

    if not orders:
        bot.reply_to(message, "📭 No active escrow orders yet.")
        return

    text = "📜 ACTIVE ESCROW ORDERS\n\n"

    for oid, data in orders.items():

        if data["status"] in ["RELEASED", "CANCELLED"]:
            continue

        text += (
            f"🧾 Order ID: {oid}\n"
            f"💰 Amount: ₹{data['amount']}\n"
            f"👤 Buyer ID: {data['user']}\n"
            f"📌 Status: {data['status']}\n"
            f"───────────────\n"
        )

    bot.reply_to(message, text)


# --------------- SAFE POLLING ----------------

print("Bot running…")

while True:
    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )
    except Exception as e:
        print("Polling error →", e)
        time.sleep(3)