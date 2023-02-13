import logging
import os
import sys
import time
import exception
import requests
from http import HTTPStatus
import telegram
from dotenv import load_dotenv
load_dotenv()


PRACTICUM_TOKEN = os.getenv('Token_Api')
TELEGRAM_TOKEN = os.getenv('Telegramm_token')
TELEGRAM_CHAT_ID = os.getenv('Chat_id')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream='sys.stdout')
logger.addHandler(handler)


def check_tokens():
    """Проверяем доступность переменных ."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет мессендж в Телеграм."""
    logger.info('отправка сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение {message}')
    except telegram.TelegramError:
        logger.error('Не удалось отправить сообщение')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    logger.info('начали запрос к API')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logger.info(f'Отправлен запрос к API сервера. '
                    f'Код ответа API: {response.status_code}')
    except requests.RequestException as error:
        raise ConnectionError(
            'Ошибка при запросе к эндпоинту! {error}'
        ) from error
    if response.status_code != HTTPStatus.OK:
        raise exception.HTTPStatusError(
            f'{ENDPOINT} недоступен! Код: {response.status_code}.')
    return response.json()


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError('В ответ API не явл.словарем')
    if 'homeworks' not in response:
        raise TypeError(
            'В ответе по ключу homeworks значений нет!')
    if 'current_date' not in response:
        raise TypeError('current_date нету в ответе API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не cодержит список')
    return homeworks


def parse_status(homework):
    """Извлекает информацию о домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'homework_name' not in homework:
        logger.error('В homework нет ключа "homework_name"')
        raise KeyError('В homework нет ключа "homework_name"')
    if "status" not in homework:
        logger.error('В homework нет ключа "status"')
        raise KeyError('В homework нет ключа "status"')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.info('Сообщение подготовлено для отправки')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют переменные ')
        sys.exit('Отсутствуют переменные ')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_status:
                    send_message(bot, message)
                    last_status = message
            else:
                logger.debug('Статус домашней работы не изменился')
            timestamp = response.get('current_date')
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
