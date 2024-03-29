import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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


logger = logging.getLogger('my_log')
logger.setLevel(logging.DEBUG)
handlers = [
    logging.StreamHandler(sys.stdout),
    logging.FileHandler('program.log', 'a', 'utf-8')
]
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s'
)
for handler in handlers:
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    logger.info('Начинаем проверку доступности переменных окружения.')
    tokens = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    check = {token: globals()[token] for token in tokens}
    if not all(check.values()):
        empty_tokens = [token for token in tokens if globals()[token] is None]
        logger.critical(f'Отсутствуют переменные {empty_tokens}.')
        raise ValueError(f'Отсутствуют переменные {empty_tokens}.')
    else:
        logger.info('Переменные окружения доступны.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту."""
    logger.info(f'Делаем запрос к {ENDPOINT}, from_date={timestamp}.')
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Ошибка {error} запроса к {ENDPOINT}, from_date={timestamp}.'
        )
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ValueError(
            f'{homework_statuses.status_code} ошибка доступа к странице.'
        )
    logger.info(
        f'Успешно выполнен запрос к {ENDPOINT}, from_date={timestamp}.'
    )
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.info('Начало проверки ответа сервера.')
    if not isinstance(response, dict):
        raise TypeError(f'В ответе API не словарь, а {type(response)}.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа `homeworks`.')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа `current_date`.')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'В ответе API под ключом `homeworks` не список, '
            f'а {type(response["homeworks"])}.'
        )
    logger.info('Проверка ответа сервера прошла успешно.')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе ее статус."""
    logger.info('Начинаем извлекать информацию о статусе домашней работе.')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name.')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status.')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неожиданный статус {status} домашней работы.')
    logger.info('Информация о статусе домашней работе успешно извлечена.')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    logger.info(f'Начинается отправка сообщения "{message}" в телеграм.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение "{message}" отправлено в телеграм.')
    except telegram.TelegramError:
        logger.error(f'Ошибка отправки сообщения "{message}" в телеграм.')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                logger.info('Статус домашней работы изменился.')
                message = parse_status(homework[0])
                if message != last_message:
                    last_message = message
                    send_message(bot, message)
            else:
                logger.info('Статус домашней работы не изменился.')
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error, exc_info=True)
            if message != last_message:
                last_message = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
