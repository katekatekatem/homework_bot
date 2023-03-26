import logging
import os
import requests

import time
import telegram

from dotenv import load_dotenv

from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


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
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s',
    encoding='utf-8'
)


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            return False
        return True


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            logging.error('Проблема с доступом к странице.')
            raise Exception(
                f'{homework_statuses.status_code} ошибка доступа к странице.'
            )
    except Exception:
        raise Exception('Ошибка запроса')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        logging.error('В ответе API не словарь.')
        raise TypeError('В ответе API не словарь.')
    if 'homeworks' not in response:
        logging.error('В ответе API нет ключа `homeworks`.')
        raise KeyError('В ответе API нет ключа `homeworks`.')
    if type(response['homeworks']) is not list:
        logging.error('В ответе API под ключом `homeworks` не список.')
        raise TypeError('В ответе API под ключом `homeworks` не список.')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе ее статус."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
    except Exception:
        logging.debug('Отсутствует новый статус.')
    if 'homework_name' not in homework:
        logging.error('Отсутствует ключ homework_name.')
        raise KeyError('Отсутствует ключ homework_name.')
    if status not in HOMEWORK_VERDICTS:
        logging.error('Неожиданный статус домашней работы.')
        raise KeyError('Неожиданный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено в телеграм')
    except Exception:
        logging.error('Ошибка отправки сообщения в телеграм')


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        logging.critical('Отсутствует токен.')
        raise KeyError('Отсутствует токен.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    # timestamp = 1677697200 # для отладки
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                if message != last_message:
                    last_message = message
                    send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(error, exc_info=True)
            if message != last_message:
                last_message = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
