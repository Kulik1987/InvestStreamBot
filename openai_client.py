import logging
import aiohttp
import config
import promts

logger = logging.getLogger(__name__)

class OpenAIClient:
    @staticmethod
    async def get_openai_response(prompt: str, history: list) -> str:
        # Добавляем последнее сообщение в историю с ролью 'user'
        history.append({
            'role': 'user',
            'content': promts.MARKETING_PROMPT + prompt
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.OPENAI_API_KEY}',
        }
        json_data = {
            'model': 'gpt-4o-mini-2024-07-18',
            'messages': history,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.openai.com/v1/chat/completions', headers=headers, json=json_data) as response:
                if response.status != 200:
                    logger.error(f'Ошибка при обращении к OpenAI: {response.text}')
                    return "Произошла ошибка при получении ответа от OpenAI."
                response_data = await response.json()
                if 'choices' not in response_data:
                    logger.error(f'Некорректный формат ответа от OpenAI: {response_data}')
                    return "Произошла ошибка при получении ответа от OpenAI."
                return response_data['choices'][0]['message']['content']
