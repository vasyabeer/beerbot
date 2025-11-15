import os
import logging
import tempfile
from flask import Flask, request, jsonify
import cv2
import numpy as np
from telegram import Bot
import requests

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# РУЧНОЕ ОПРЕДЕЛЕНИЕ ПЕРЕМЕННЫХ - ЗАМЕНИТЕ НА СВОИ ЗНАЧЕНИЯ
TOKEN = "8222564910:AAHsVTZcn_O5NhbluSo6_Vau1BrdLsvZHRo"  # Замените на токен от BotFather
WEBHOOK_URL = "https://beerbot-1-rz63.onrender.com"  # Замените на ваш URL на Render
PORT = int(os.environ.get('PORT', 5000))

app = Flask(__name__)

# Инициализация бота
bot = Bot(token=TOKEN) if TOKEN and TOKEN != "ВАШ_ТОКЕН_БОТА" else None

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

@app.route('/')
def home():
    return jsonify({
        "status": "Beer Bot работает! 🍻",
        "mode": "production",
        "token_set": bool(bot),
        "webhook_url": WEBHOOK_URL,
        "instructions": "Проверьте настройки в /settings"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "bot_initialized": bool(bot)})

@app.route('/settings')
def settings():
    """Показывает текущие настройки"""
    current_token = "НЕ УСТАНОВЛЕН" if not bot else "УСТАНОВЛЕН (скрыт)"
    return jsonify({
        "bot_initialized": bool(bot),
        "webhook_url": WEBHOOK_URL,
        "port": PORT,
        "instructions": {
            "1": "Замените TOKEN и WEBHOOK_URL в коде app.py",
            "2": "Перезапустите приложение на Render",
            "3": "Откройте /set_webhook для установки вебхука",
            "4": "Протестируйте бота в Telegram"
        }
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик вебхука от Telegram"""
    try:
        if not bot:
            logger.error("Бот не инициализирован. Проверьте токен.")
            return "ERROR: Bot not initialized", 500
        
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
                    bot.send_message(
                        chat_id=chat_id,
                        text="🍻 Привет! Я Beer Bot! 🍻\n\n"
                             "Отправь мне фото человека или животного, и я добавлю кружку пива!\n\n"
                             "Просто отправь любое фото и увидишь магию!"
                    )
                elif text == '/test':
                    bot.send_message(chat_id, "✅ Бот работает! Отправь фото для теста.")
                else:
                    bot.send_message(chat_id, "Отправь мне фото, и я добавлю кружку пива! 🍻")
            
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
        bot.send_message(chat_id, "🍻 Обрабатываю фото... Добавляю кружку пива!")
        
        # Берем фото наибольшего качества (последнее в массиве)
        photo = message['photo'][-1]
        file_id = photo['file_id']
        
        # Получаем информацию о файле
        file_info = bot.get_file(file_id)
        if not file_info:
            bot.send_message(chat_id, "❌ Не удалось получить информацию о файле")
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
                bot.send_message(chat_id, "❌ Не удалось загрузить фото")
                return
            
            # Обрабатываем изображение
            if not add_beer_to_image(input_path, output_path):
                bot.send_message(chat_id, "❌ Не удалось обработать фото")
                return
            
            # Отправляем результат
            with open(output_path, 'rb') as photo_file:
                bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_file,
                    caption="🎉 Ваше фото с кружкой пива! 🍻"
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
            bot.send_message(message['chat']['id'], "❌ Произошла ошибка при обработке фото")
        except:
            pass

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    """Установка вебхука"""
    try:
        if not bot:
            return jsonify({
                "error": "Бот не инициализирован. Проверьте токен в коде.",
                "instructions": "Замените TOKEN в app.py на ваш токен от BotFather"
            }), 400
        
        if not WEBHOOK_URL or WEBHOOK_URL == "https://your-app-name.onrender.com":
            return jsonify({
                "error": "WEBHOOK_URL не установлен",
                "instructions": "Замените WEBHOOK_URL в app.py на ваш URL с Render"
            }), 400
        
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = bot.set_webhook(webhook_url)
        
        logger.info(f"Вебхук установлен: {webhook_url}")
        
        return jsonify({
            "status": "success",
            "webhook_url": webhook_url,
            "result": result,
            "message": "Вебхук успешно установлен! Теперь можете тестировать бота в Telegram."
        })
        
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/remove_webhook', methods=['GET'])
def remove_webhook_route():
    """Удаление вебхука"""
    try:
        if not bot:
            return jsonify({"error": "Бот не инициализирован"}), 400
        
        result = bot.delete_webhook()
        
        return jsonify({
            "status": "success", 
            "result": result,
            "message": "Вебхук удален"
        })
        
    except Exception as e:
        logger.error(f"Ошибка удаления вебхука: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """Информация о вебхуке"""
    try:
        if not bot:
            return jsonify({"error": "Бот не инициализирован"}), 400
        
        info = bot.get_webhook_info()
        
        return jsonify({
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о вебхуке: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Запуск Beer Bot на Render")
    logger.info(f"📝 PORT: {PORT}")
    logger.info(f"🔑 Bot инициализирован: {bool(bot)}")
    logger.info(f"🌐 WEBHOOK_URL: {WEBHOOK_URL}")
    
    if not bot:
        logger.error("❌ Бот не инициализирован! Замените TOKEN в коде на ваш токен.")
        logger.info("💡 Инструкция:")
        logger.info("1. Получите токен у @BotFather в Telegram")
        logger.info("2. Замените 'ВАШ_ТОКЕН_БОТА' в коде app.py на ваш токен")
        logger.info("3. Замените WEBHOOK_URL на ваш URL с Render")
        logger.info("4. Перезапустите приложение")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
