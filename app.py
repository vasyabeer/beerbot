import os
import logging
import tempfile
import asyncio
from flask import Flask, request, jsonify
import cv2
import numpy as np
from telegram import Bot
from telegram.error import TelegramError
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
PORT = int(os.environ.get('PORT', 5000))

app = Flask(__name__)

# Глобальная переменная для бота
bot = None

def init_bot():
    """Инициализация бота"""
    global bot
    if TOKEN:
        bot = Bot(token=TOKEN)
    return bot

def create_beer_mug():
    """Создает кружку пива программно"""
    size = 200
    beer_mug = np.zeros((size, size, 4), dtype=np.uint8)
    
    # Основная часть кружки (янтарный цвет пива)
    cv2.rectangle(beer_mug, (60, 50), (140, 180), (50, 100, 200, 255), -1)
    
    # Пена
    cv2.rectangle(beer_mug, (60, 30), (140, 60), (255, 255, 255, 255), -1)
    
    # Ручка
    cv2.ellipse(beer_mug, (150, 120), (25, 40), 0, 270, 90, (100, 70, 30, 255), -1)
    
    # Ободок
    cv2.rectangle(beer_mug, (55, 45), (145, 55), (100, 70, 30, 255), -1)
    cv2.rectangle(beer_mug, (55, 175), (145, 185), (100, 70, 30, 255), -1)
    
    return beer_mug

def add_beer_to_image(input_path, output_path):
    """Добавляет кружку пива на изображение"""
    try:
        original_image = cv2.imread(input_path)
        if original_image is None:
            logger.error("Не удалось загрузить изображение")
            return False
        
        beer_mug = create_beer_mug()
        img_height, img_width = original_image.shape[:2]
        beer_height, beer_width = beer_mug.shape[:2]
        
        # Масштабируем кружку
        scale = min(img_width, img_height) * 0.2 / beer_width
        new_width = int(beer_width * scale)
        new_height = int(beer_height * scale)
        beer_mug_resized = cv2.resize(beer_mug, (new_width, new_height))
        
        # Позиция в правом нижнем углу
        x_pos = img_width - new_width - 20
        y_pos = img_height - new_height - 20
        x_pos = max(0, min(x_pos, img_width - new_width))
        y_pos = max(0, min(y_pos, img_height - new_height))
        
        logger.info(f"Размер изображения: {img_width}x{img_height}, Позиция кружки: ({x_pos}, {y_pos})")
        
        # Накладываем кружку с прозрачностью
        for y in range(new_height):
            for x in range(new_width):
                if y + y_pos < img_height and x + x_pos < img_width:
                    alpha = beer_mug_resized[y, x, 3] / 255.0
                    if alpha > 0:
                        for channel in range(3):
                            original_image[y + y_pos, x + x_pos, channel] = (
                                alpha * beer_mug_resized[y, x, channel] +
                                (1 - alpha) * original_image[y + y_pos, x + x_pos, channel]
                            )
        
        success = cv2.imwrite(output_path, original_image)
        logger.info(f"Изображение сохранено: {success}")
        return success
        
    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {str(e)}")
        return False

def download_file(url, local_path):
    """Скачивает файл по URL"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {str(e)}")
        return False

def sync_send_message(chat_id, text):
    """Синхронная отправка сообщения"""
    try:
        if bot:
            # Используем run для синхронного выполнения асинхронной функции
            asyncio.run(bot.send_message(chat_id=chat_id, text=text))
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {str(e)}")

def sync_send_photo(chat_id, photo_path, caption=None):
    """Синхронная отправка фото"""
    try:
        if bot:
            with open(photo_path, 'rb') as photo:
                asyncio.run(bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption
                ))
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {str(e)}")

def sync_get_file(file_id):
    """Синхронное получение информации о файле"""
    try:
        if bot:
            return asyncio.run(bot.get_file(file_id))
    except Exception as e:
        logger.error(f"Ошибка получения файла: {str(e)}")
    return None

@app.route('/')
def home():
    return jsonify({
        "status": "Beer Bot работает! 🍻",
        "mode": "локальный",
        "token_set": bool(TOKEN),
        "endpoints": {
            "health": "/health",
            "set_webhook": "/set_webhook (только для production)",
            "test": "/test"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "token_set": bool(TOKEN)})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик вебхука от Telegram"""
    try:
        if not TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN не установлен")
            return "ERROR: Token not configured", 500
        
        update_data = request.get_json()
        if not update_data:
            return "No data", 400
        
        # Обрабатываем сообщение
        if 'message' in update_data:
            message = update_data['message']
            
            # Текстовое сообщение
            if 'text' in message:
                chat_id = message['chat']['id']
                text = message['text'].lower()
                
                if text in ['/start', '/help']:
                    sync_send_message(
                        chat_id,
                        "🍻 Привет! Я Beer Bot! 🍻\n\n"
                        "Отправь мне фото человека или животного, и я добавлю кружку пива!\n\n"
                        "Просто отправь любое фото и увидишь магию!\n\n"
                        "Режим: Локальный запуск"
                    )
                elif text == '/test':
                    sync_send_message(chat_id, "✅ Бот работает! Отправь фото для теста.")
                else:
                    sync_send_message(chat_id, "Отправь мне фото, и я добавлю кружку пива! 🍻")
            
            # Фото
            elif 'photo' in message:
                process_photo_message(message)
        
        return "OK"
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return "ERROR", 500

def process_photo_message(message):
    """Обработка фото сообщения"""
    try:
        chat_id = message['chat']['id']
        
        logger.info("Обработка фото...")
        sync_send_message(chat_id, "🍻 Обрабатываю фото... Добавляю кружку пива!")
        
        # Берем фото наибольшего качества (последнее в массиве)
        photo = message['photo'][-1]
        file_id = photo['file_id']
        
        # Получаем информацию о файле
        file_info = sync_get_file(file_id)
        if not file_info:
            sync_send_message(chat_id, "❌ Не удалось получить информацию о файле")
            return
        
        file_url = file_info.file_path
        
        # Создаем временные файлы
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as input_file:
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Скачиваем фото
            download_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_url}"
            if not download_file(download_url, input_path):
                sync_send_message(chat_id, "❌ Не удалось загрузить фото")
                return
            
            # Обрабатываем изображение
            if not add_beer_to_image(input_path, output_path):
                sync_send_message(chat_id, "❌ Не удалось обработать фото")
                return
            
            # Отправляем результат
            sync_send_photo(
                chat_id=chat_id,
                photo_path=output_path,
                caption="🎉 Ваше фото с кружкой пива! 🍻\n(Локальный режим)"
            )
            logger.info("Фото успешно обработано и отправлено")
                
        finally:
            # Удаляем временные файлы
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception as e:
                        logger.error(f"Ошибка удаления временного файла: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {str(e)}")
        try:
            sync_send_message(message['chat']['id'], "❌ Произошла ошибка при обработке фото")
        except:
            pass

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    """Установка вебхука - только для production"""
    return jsonify({
        "status": "info",
        "message": "В локальном режиме вебхук не используется. Для тестирования используйте polling или ngrok."
    })

@app.route('/test', methods=['GET'])
def test():
    """Тестовый endpoint"""
    try:
        if not TOKEN:
            return jsonify({"error": "Токен не установлен"}), 400
        
        # Простая проверка бота
        sync_send_message(chat_id=0000000, text="Тестовое сообщение")  # Неправильный chat_id для теста
        
        return jsonify({
            "status": "success",
            "message": "Бот инициализирован",
            "token_set": bool(TOKEN)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/demo', methods=['GET'])
def demo():
    """Демонстрация обработки изображения"""
    try:
        # Создаем тестовое изображение
        test_img = np.ones((400, 400, 3), dtype=np.uint8) * 255
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as input_file:
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as output_file:
            output_path = output_file.name
        
        cv2.imwrite(input_path, test_img)
        success = add_beer_to_image(input_path, output_path)
        
        # Чистим
        for path in [input_path, output_path]:
            if os.path.exists(path):
                os.unlink(path)
        
        return jsonify({
            "demo": "success" if success else "failed",
            "message": "Обработка изображения работает" if success else "Ошибка обработки"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Инициализируем бота
    init_bot()
    
    logger.info("🚀 Запуск Beer Bot в локальном режиме")
    logger.info(f"📝 PORT: {PORT}")
    logger.info(f"🔑 Token установлен: {bool(TOKEN)}")
    
    if not TOKEN:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN не установлен! Создайте файл .env")
        logger.info("💡 Пример .env файла:")
        logger.info("TELEGRAM_BOT_TOKEN=your_token_here")
        logger.info("WEBHOOK_URL=http://localhost:5000")
    
    app.run(host='0.0.0.0', port=PORT, debug=True)
