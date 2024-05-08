import logging
import os
import sys
import time
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import HomeworkStatusError, TokensError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('MY_PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('MY_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('MY_TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие обязательных переменных окружения."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logging.critical('Отсутствуют обязательные переменные окружения.')
        raise TokensError('Отсутствуют обязательные переменные окружения.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено в Telegram.')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != 200:
            logging.error(f'Эндпоинт недоступен: {response.status_code}')
            raise requests.HTTPError(
                f'Эндпоинт недоступен: {response.status_code}'
            )
        return response.json()
    except requests.RequestException as error:
        logging.error(f'Ошибка при выполнении запроса: {error}')
        raise Exception(f'Ошибка при выполнении запроса: {error}')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        logging.error('Ответ API не является словарем.')
        raise TypeError('Ответ API не является словарем.')

    homeworks = response.get('homeworks')

    if homeworks is None:
        logging.error('В ответе API нет ключа `homeworks`.')
        raise KeyError('В ответе API нет ключа `homeworks`.')
    elif not isinstance(homeworks, list):
        logging.error('Ключ `homeworks` не является списком.')
        raise TypeError('Ключ `homeworks` не является списком.')
    elif not homeworks:
        logging.debug('Статус домашней работы не изменился.')
        return False
    return True


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        logging.error('В ответе API нет ключа `homework_name`.')
        raise KeyError('В ответе API нет ключа `homework_name`.')

    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error(
            f'Неизвестное значение статуса домашней работы: {homework_status}'
        )
        raise HomeworkStatusError(
            f'Неизвестное значение статуса домашней работы: {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    last_exception = None

    while True:
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                last_homework = response.get('homeworks')[0]
                message = parse_status(last_homework)
                send_message(bot, message)
                timestamp = timestamp + RETRY_PERIOD
        except Exception as error:
            if last_exception != error:
                message = f'Сбой в работе программы: {error}'
                bot.send_message(TELEGRAM_CHAT_ID, message)
            last_exception = error
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
