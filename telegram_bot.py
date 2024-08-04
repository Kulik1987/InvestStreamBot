from telethon import TelegramClient, events, Button
from telethon.tl.types import Channel, PeerChannel
from telethon.errors.rpcerrorlist import ChannelPrivateError, ChatAdminRequiredError
import logging
import config
from openai_client import OpenAIClient
from telethon.errors import FloodWaitError
import asyncio
import os
import glob

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
# chat_id invest_stream = -1001474010780
# ID администратора
ADMIN_IDS = [707717005, 215142869, 815456809]
chat_id= int(config.TELEGRAM_CHAT_ID)

# Настройка клиента Telethon
api_id = config.API_ID
api_hash = config.API_HASH
bot_token = config.TELEGRAM_BOT_TOKEN

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

class TelegramBot:
    def __init__(self, client):
        self.client = client
        self.expecting_image = {}
        self.awaiting_response = {}
        self.awaiting_broadcast_message = False  # Для отслеживания ожидания текстового сообщения
        self.running = True  # Флаг для работы функции логирования

    async def start(self, event):
        sender = await event.get_sender()
        user_id = sender.id
        if user_id in ADMIN_IDS:
            buttons = [
                [Button.text('Загрузить анонс'), Button.text('Создать сообщение')],
                [Button.text('Разослать анонс'), Button.text('Разослать сообщение')]
            ]
            await self.client.send_message(
                event.chat_id,
                'Вы можете загрузить анонс, создать сообщение или отправить рассылку.',
                buttons=buttons
            )

    async def message_handler(self, event):
        sender = await event.get_sender()
        user_id = sender.id

        if user_id in ADMIN_IDS:
            text = event.raw_text
            if text == 'Загрузить анонс':
                logger.info('Кнопка Загрузить анонс нажата')
                await event.respond("Выберите картинку для анонса.")
                self.expecting_image[user_id] = True
            elif text == 'Создать сообщение':
                logger.info('Кнопка Создать сообщение нажата')
                await event.respond("Пожалуйста, введите ваше сообщение:")
                self.awaiting_response[user_id] = True
            elif text == 'Разослать анонс':
                logger.info('Кнопка Разослать анонс нажата')
                await self.send_announcement_to_group()
            elif text == 'Разослать сообщение':
                logger.info('Кнопка Разослать сообщение нажата')
                await event.respond("Пожалуйста, введите сообщение для рассылки:")
                self.awaiting_broadcast_message = True
            elif self.awaiting_broadcast_message:
                logger.info(f'Получено сообщение для рассылки: {text}')
                await self.send_broadcast_message(text)
                self.awaiting_broadcast_message = False
            elif self.awaiting_response.get(user_id, False):
                logger.info(f'Получено сообщение от пользователя для OpenAI: {text}')
                await self.handle_openai_response(event, text)
        else:
            await event.respond('''👋 Привет! Добро пожаловать в телеграм-бот бизнес-клуба Invest Stream! 📈 Здесь вы найдете анонсы самых интересных мероприятий по инвестициям и бизнесу! 💼

            Наш бот поможет вам не пропустить ни одно важное событие: мастер-классы, вебинары, встречи с успешными предпринимателями и многое другое! 🚀 Просто подпишитесь и получайте уведомления о новых мероприятиях. 📲

            Оставайтесь в курсе всех актуальных трендов и обретите новые знания вместе с нами! 🎓 Не упустите возможность развивать свои навыки и расширять сеть деловых контактов! 🌐''')

    async def handle_openai_response(self, event, prompt):
        self.awaiting_response[event.sender_id] = False
        history = []  # Начинаем с пустой истории
        response = await OpenAIClient.get_openai_response(prompt, history)
        await event.respond(response)

    async def file_handler(self, event):
        user_id = event.sender_id
        logger.info('Обработка файла началась')

        # Удаление всех файлов в директории load_data
        folder_path = 'load_data'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        else:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        os.rmdir(file_path)
                except Exception as e:
                    logger.error(f'Не удалось удалить {file_path}. Причина: {e}')

        if self.expecting_image.get(user_id, False):
            logger.info('Проверка: ожидается загрузка изображения')
            if event.document or event.photo:
                file_path = 'load_data/announcement'
                if event.document:
                    mime_type = event.document.mime_type
                    logger.info(f'Получен документ с mime-типом: {mime_type}')
                    file_extension = mime_type.split('/')[1]
                    file_path += f'.{file_extension}'
                elif event.photo:
                    logger.info('Получено фото')
                    file_path += '.jpg'
                await self.client.download_media(event.message, file_path)
                await event.respond(f'Изображение успешно загружено и сохранено как {file_path}.')
                self.expecting_image[user_id] = False
            else:
                logger.info('Документ не найден в сообщении')
        else:
            logger.info('Не ожидается загрузка изображения, пропускаем обработку файла.')

    async def get_group_members(self, group_id):
        try:
            members = []
            async for member in self.client.iter_participants(group_id):
                members.append(member)
            return members
        except (ChatAdminRequiredError, ChannelPrivateError) as e:
            logger.error(f"Ошибка доступа к участникам группы: {e}")
            return []
        except Exception as e:
            logger.error(f'Ошибка при получении участников группы: {e}')
            return []

    async def list_group_members(self, event):
        try:
            full_channel = await client.get_entity(PeerChannel(chat_id))
            logger.info(f'Полная сущность канала: {full_channel}')
        except (ChannelPrivateError, ChatAdminRequiredError) as e:
            await event.respond(f"Ошибка доступа к каналу: {e}")
            logger.error(f"Ошибка доступа к каналу: {e}")
            return
        except Exception as e:
            logger.error(f'Ошибка при получении сущности канала: {e}')
            await event.respond("Произошла ошибка при попытке получить данные о группе.")
            return

        if isinstance(full_channel, Channel) and full_channel.megagroup:
            try:
                members = await client.get_participants(full_channel)
                if not members:
                    await event.respond("Не удалось получить список участников. Убедитесь, что бот имеет права администратора.")
                else:
                    member_usernames = [member.username or member.id for member in members]
                    message = f'В группе {len(members)} участников. Пользователи: {", ".join(str(username) for username in member_usernames)}'
                    await event.respond(message)
            except Exception as e:
                logger.error(f'Ошибка при получении участников: {e}')
                await event.respond("Произошла ошибка при попытке получить участников группы.")
        else:
            await event.respond("Этот чат не является супергруппой.")

    async def send_message_to_members(self, members, message):
        for member in members:
            try:
                if member.bot:
                    continue
                if not member.username and not member.phone:
                    continue
                await self.client.send_message(member.id, message)
                logger.info(f"Сообщение отправлено пользователю {member.id}")
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(f"Переполнение: задержка на {e.seconds} секунд.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {member.id}: {e}")


    async def send_announcement_to_group(self):
        # Поиск файла с именем 'announcement' и любым расширением в папке load_data
        file_pattern = 'load_data/announcement.*'
        files = glob.glob(file_pattern)
        if not files:
            logger.error("Файл 'announcement' не найден в директории 'load_data'.")
            await event.respond("Список участников пуст или не удалось его получить.")
            return

        image_path = files[0]  # Предполагается, что найден только один файл

        try:
            full_channel = await client.get_entity(PeerChannel(chat_id))
        except Exception as e:
            logger.error(f'Ошибка при получении сущности канала для рассылки анонса: {e}')
            return

        if not isinstance(full_channel, Channel) or not full_channel.megagroup:
            logger.error("Этот чат не является супергруппой.")
            return

        members = await self.get_group_members(chat_id)
        if not members:
            logger.info("Список участников пуст или не удалось его получить.")
            await event.respond("Список участников пуст или не удалось его получить.")
            return

        for member in members:
            try:
                if member.bot:
                    continue
                if not member.username and not member.phone:
                    continue
                await self.client.send_file(member.id, image_path, caption="Анонс")
                logger.info(f"Изображение отправлено пользователю {member.id}")
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(f"Переполнение: задержка на {e.seconds} секунд.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения пользователю {member.id}: {e}")

    async def send_broadcast_message(self, message):
        try:
            full_channel = await client.get_entity(PeerChannel(chat_id))
        except Exception as e:
            logger.error(f'Ошибка при получении сущности канала для рассылки сообщения: {e}')
            return

        if not isinstance(full_channel, Channel) or not full_channel.megagroup:
            logger.error("Этот чат не является супергруппой.")
            return

        members = await self.get_group_members(chat_id)
        if not members:
            logger.info("Список участников пуст или не удалось его получить.")
            await event.respond("Список участников пуст или не удалось его получить.")
            return

        for member in members:
            try:
                if member.bot:
                    continue
                if not member.username and not member.phone:
                    continue
                await self.client.send_message(member.id, message)
                logger.info(f"Сообщение отправлено пользователю {member.id}")
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(f"Переполнение: задержка на {e.seconds} секунд.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {member.id}: {e}")

    def run(self):
        self.client.on(events.NewMessage(pattern='/start'))(self.start)
        self.client.on(events.NewMessage(incoming=True))(self.message_handler)
        self.client.on(events.NewMessage(incoming=True, func=lambda e: e.document or e.photo))(self.file_handler)
        self.client.run_until_disconnected()
