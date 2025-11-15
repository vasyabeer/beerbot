import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from PIL import Image
import mediapipe as mp
import tempfile
import os

TOKEN = "8222564910:AAHsVTZcn_O5NhbluSo6_Vau1BrdLsvZHRo"

logging.basicConfig(level=logging.INFO)

mp_hands = mp.solutions.hands

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        await file.download_to_drive(tmp.name)
        img_path = tmp.name

    image = Image.open(img_path).convert("RGB")

    with mp_hands.Hands(static_image_mode=True, max_num_hands=1) as hands:
        import cv2
        import numpy as np

        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        results = hands.process(cv_img)

        if not results.multi_hand_landmarks:
            await update.message.reply_text("Не удалось определить руку. Пришли фото целиком.")
            return

        landmark = results.multi_hand_landmarks[0].landmark[mp_hands.HandLandmark.WRIST]
        h, w, _ = cv_img.shape

        x = int(landmark.x * w)
        y = int(landmark.y * h)

    beer = Image.open("beer.png").convert("RGBA")
    beer = beer.resize((int(w * 0.25), int(w * 0.25)))

    image.paste(beer, (x, y), beer)

    out_path = img_path + "_out.jpg"
    image.save(out_path)

    await update.message.reply_photo(photo=open(out_path, "rb"))

    os.remove(img_path)
    os.remove(out_path)


async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        url_path=TOKEN,
        webhook_url=f"https://{os.environ['RAILWAY_STATIC_URL']}/{TOKEN}"
    )

import asyncio
asyncio.run(main())
