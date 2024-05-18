import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

from exceptions import CustomExceptionError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 10 * 60
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        logging.debug(f'Нужно отправить: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Успешно отправил: {message}')
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения: {message}. Ошибка {error}')


def get_api_answer(timestamp):
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise CustomExceptionError(f'Статус код: {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        raise CustomExceptionError(f'Ошибка: {error}')


def check_response(response):
    """Проверяет ответ API."""
    logging.info('Проверяем ответ')
    if not isinstance(response, dict):
        raise TypeError('Ответ API имеет неккоректный формат')
    if 'current_date' not in response:
        raise KeyError('отсутствует ключ "current_date"')
    if 'homeworks' not in response:
        raise TypeError('Отсутствует ключ "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ "homeworks" не имеет значения в формате списка')
    logging.info('Ответ получен и соответствует требованиям.')
    return response['homeworks']


def parse_status(homework):
    """Проверяет статус домашней работы."""
    logging.info('Проверяем статус работы')
    status = homework.get('status')
    if status is None:
        raise KeyError('отсутствует ключ "status"')
    if not isinstance(status, str):
        raise KeyError('статус не соответствует str')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('отсутствует ключ "homework_name"')
    if not isinstance(homework_name, str):
        raise KeyError('"homework_name" не является строкой')
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        raise KeyError(f'Недокументированный статус: {status}')
    logging.info('Статус домашней работы корректен')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'отсутствие обязательных переменных окружения',
            'во время запуска бота, бот остановлен'
        )
        sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homework = check_response(api_answer)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
                timestamp = int(time.time())
            else:
                logging.debug("Статус не изменился")

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename='main.log',
        format='%(asctime)s, %(levelname)s, %(name)s,'
        '%(message)s, %(created)f'
    )
    logging.StreamHandler(sys.stdout)
    logging.FileHandler('spam.log')
    main()
