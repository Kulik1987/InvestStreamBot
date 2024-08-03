from telegram_bot import TelegramBot, client


def main() -> None:
    # Запуск Telegram бота
    telegram_bot = TelegramBot(client)
    telegram_bot.run()

if __name__ == '__main__':
    main()

