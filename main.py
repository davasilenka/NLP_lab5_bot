import telebot
import requests
import jsons
from Class_ModelResponse import ModelResponse

# Замените 'YOUR_BOT_TOKEN' на ваш токен от BotFather
API_TOKEN = 'ВАШ ТОКЕН'
bot = telebot.TeleBot(API_TOKEN)

user_contexts = {}

# Максимальное количество пар "запрос-ответ"
MAX_CONTEXT_LENGTH = 10

def build_messages_from_history(history: str):
    """Преобразуем строку истории в список сообщений для API."""
    messages = []
    lines = history.strip().split('\n')

    for line in lines:
        if line.startswith('user:'):
            messages.append({"role": "user", "content": line[5:].strip()})
        elif line.startswith('assistant:'):
            messages.append({"role": "assistant", "content": line[10:].strip()})

    return messages


def truncate_history(history: str):
    """Обрезаем историю, если она слишком длинная, оставляя последние MAX_CONTEXT_LENGTH (10) пар."""
    lines = history.strip().split('\n')
    if len(lines) > MAX_CONTEXT_LENGTH * 2:
        lines = lines[-MAX_CONTEXT_LENGTH * 2:]
    return '\n'.join(lines)


# Команды
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я ваш Telegram бот.\n"
        "Доступные команды:\n"
        "/start - вывод всех доступных команд\n"
        "/model - выводит название используемой языковой модели\n"
        "/clear - полностью очищает историю нашего диалога\n"
        "Отправьте любое сообщение, и я отвечу с помощью LLM модели."
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['model'])
def send_model_name(message):
    # Отправляем запрос к LM Studio для получения информации о модели
    response = requests.get('http://localhost:1234/v1/models')

    if response.status_code == 200:
        model_info = response.json()
        model_name = model_info['data'][0]['id']
        bot.reply_to(message, f"Используемая модель: {model_name}")
    else:
        bot.reply_to(message, 'Не удалось получить информацию о модели.')


@bot.message_handler(commands=['clear'])
def clear_context(message):
    user_id = message.from_user.id

    if user_id in user_contexts:
        # Удаляем историю пользователя
        del user_contexts[user_id]
        bot.reply_to(message, "Контекст диалога очищен. Начинаем общение заново!")
    else:
        # Если истории ещё не было
        bot.reply_to(message, "У вас ещё нет истории диалога для очистки.")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_query = message.text

    # Получаем или создаем историю для пользователя
    if user_id not in user_contexts:
        user_contexts[user_id] = ""

    # Добавляем новый запрос пользователя в историю
    user_contexts[user_id] += f"user: {user_query}\n"

    # Обрезаем историю, если она слишком длинная
    user_contexts[user_id] = truncate_history(user_contexts[user_id])

    # Преобразуем историю в формат для API
    messages = build_messages_from_history(user_contexts[user_id])

    request = {
        "messages": messages,
        "temperature": 0.7,   # Параметр креативности
        "max_tokens": 300     # 200-250 слов на ответ максимум
    }

    # Отправляем запрос к модели
    response = requests.post(
        'http://localhost:1234/v1/chat/completions',
        json=request
    )

    if response.status_code == 200:
        model_response: ModelResponse = jsons.loads(response.text, ModelResponse)
        bot_reply = model_response.choices[0].message.content

        # Добавляем ответ модели в историю
        user_contexts[user_id] += f"assistant: {bot_reply}\n"

        # Отправляем ответ пользователю
        bot.reply_to(message, bot_reply)

    else:
        # Если ошибка, удаляем последний запрос пользователя из истории
        user_contexts[user_id] = user_contexts[user_id].replace(f"user: {user_query}\n", "")
        bot.reply_to(message, 'Произошла ошибка при обращении к модели.')


if __name__ == '__main__':
    print("Бот запущен с поддержкой контекста...")

    bot.polling(none_stop=True)
