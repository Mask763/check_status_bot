import functools
import logging
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telebot import TeleBot, telebot

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(lineno)d, %(funcName)s, %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие обязательных переменных окружения."""
    required_vars = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    global_vars = globals()
    missing_vars = [var for var in required_vars if not global_vars.get(var)]

    if missing_vars:
        logger.critical(
            f'Отсутствуют обязательные переменные окружения: {missing_vars}'
        )
        raise ValueError(
            f'Отсутствуют обязательные переменные окружения: {missing_vars}'
        )


def message_validator(func):
    """Функция-декоратор для защиты от повторяющегося сообщения."""
    previous_message = ''

    @functools.wraps(func)
    def wrapper(bot, message):
        nonlocal previous_message

        if message != previous_message:
            func(bot, message)
            previous_message = message
        else:
            logger.debug('Полуено повторяющееся сообщение. Пропускаю.')

    return wrapper


@message_validator
def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    logger.debug('Пытаюсь отправить сообщение в Telegram.')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug('Сообщение успешно отправлено в Telegram.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    logger.debug('Начинаю запрос к эндпоинту API-сервиса.')
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Ошибка при выполнении запроса к эндпоинту {ENDPOINT} с '
            f'параметром {timestamp}: {error}'
        )

    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            f'Эндпоинт {ENDPOINT} с параметром {timestamp} '
            f'недоступен: {response.status_code}'
        )

    logger.debug('Запрос к эндпоинту API-сервиса успешно выполнен.')
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.debug('Проверяю ответ API на корректность.')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем. '
                        f'Получен тип данных: {type(response)}')

    homeworks = response.get('homeworks')

    if homeworks is None:
        raise KeyError('В ответе API нет ключа `homeworks`.')
    elif not isinstance(homeworks, list):
        raise TypeError('Ключ `homeworks` не является списком. '
                        f'Получен тип данных: {type(homeworks)}')

    logger.debug('Ответ API корректен.')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logger.debug('Извлекаю статус домашней работы.')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('В ответе API нет ключа `homework_name`.')

    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неизвестное значение статуса домашней работы: {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.debug('Статус домашней работы успешно извлечен.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            if homeworks:
                last_homework = homeworks[0]
                message = parse_status(last_homework)
                send_message(bot, message)
                timestamp = int(time.time())
            else:
                logger.debug('Статус домашней работы не изменился.')
        except telebot.apihelper.ApiException as error:
            logger.error(f'Сбой при отправке сообщения: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            with suppress(telebot.apihelper.ApiException):
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
