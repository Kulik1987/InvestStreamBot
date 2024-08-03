from telegram_bot import TelegramBot, client
from flask import Flask, jsonify
import threading

# Создаем экземпляр Flask
app = Flask(__name__)

# Глобальная переменная для состояния бота
bot_running = False

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint для проверки состояния бота."""
    if bot_running:
        return jsonify(status="UP"), 200
    else:
        return jsonify(status="DOWN"), 503

def start_flask_app():
    """Запуск Flask-приложения."""
    app.run(host='0.0.0.0', port=5000)

def main() -> None:
    global bot_running

    # Запуск Flask-приложения в отдельном потоке
    flask_thread = threading.Thread(target=start_flask_app)
    flask_thread.start()

    # Запуск Telegram бота
    try:
        telegram_bot = TelegramBot(client)
        bot_running = True
        telegram_bot.run()
    finally:
        bot_running = False

if __name__ == '__main__':
    main()
