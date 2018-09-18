#!/usr/bin/env python
# -*- coding: utf-8 -*-


from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import logging
import os
import urllib
import json
import requests

try:
    from urllib.request import Request, urlopen
except ImportError: # Python 2
    from urllib2 import Request, urlopen, HTTPError


TG_TOKEN = os.getenv('TG_TOKEN', "")
TG_CHAT_IDS = os.getenv('TG_CHAT_IDS', "")
TG_CHAT_LST = []

API_KEY = os.getenv('API_KEY', "")
API_TOKEN = '' # empty at start
API_BASE_URL = "https://api.remonline.ru/"
API_MAX_RETRIES = 5

DEBUG = os.getenv('DEBUG', False)
HTTP_CLIENT_TIMEOUT = 5

EMPLOYEES = {}

if DEBUG:
    log_lvl = logging.DEBUG
else:
    log_lvl = logging.INFO

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=log_lvl)

logger = logging.getLogger(__name__)


def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z


def remonline_api_renew_token(api_key=API_KEY):

    global API_TOKEN
    url = "{}{}".format(API_BASE_URL, 'token/new')
    r = requests.post(url, {"api_key": api_key})
    if r.status_code == 200:
        ret = r.json()
        if ret['success']:
            return ret['token']
        else:
            logger.error('Renew token return 200, but success = false')
            logger.debug('Response text: "%s"', r.text)
    else:
        logger.error('Error while try to renew token. Code "%s", Body "%s"')

    return None


def remonline_api_get(api_path, token=API_TOKEN, filters={}, page=1, retries=0):

    if retries > API_MAX_RETRIES:
        logger.error('Cant handle request to api_path "%s" max retries number "%s" reached', api_path, API_MAX_RETRIES)
        return None

    url = "{}{}".format(API_BASE_URL, api_path)
    data_values = merge_two_dicts({'token': token, 'page': page}, filters)

    r = requests.get(url, data_values)
    logger.debug('API request to "%s" with filters "%s" return code "%s" and data "%s"',
                 url, filters, r.status_code, r.text)
    if r.status_code == 200:
        return r.json()

    elif r.status_code == 403:
        new_token = remonline_api_renew_token()
        if new_token:
            return remonline_api_get(api_path, new_token, filters, page, retries + 1)

    return None


def start(bot, update):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi!')


def help(bot, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def echo(bot, update):
    """Echo the user message."""
    update.message.reply_text(update.message.text)


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def get_orders(bot, update):
    """ Get orders from external system """
    result = remonline_api_get('order/')
    orders_lst = []
    for o in result['data']:
        if o['status']['group'] in [6, 7]:
            # we don't need closed and canceled orders
            continue
        if o['engineer_id'] in EMPLOYEES:
            engineer = EMPLOYEES[o['engineer_id']]['first_name'] + ' ' + EMPLOYEES[o['engineer_id']]['last_name']
        else:
            engineer = '=FREE='
        orders_lst.append(" ".join([o['id_label'], o['client']['name'], '(', o['status']['name'], ')', engineer]))
    orders_str = '\n'.join(orders_lst)
    update.message.reply_text(orders_str)


def client_list(bot, update):
    """ Get client list from external system """
    result = remonline_api_get('clients/')
    client_lst = []
    for cl in result['data']:
        client_lst.append(cl['name'])
    clients_str = '\n'.join(client_lst)
    update.message.reply_text(clients_str)


def status_list(bot, update):
    """ Get status list from external system """
    result = remonline_api_get('statuses/')
    s_lst = []
    for s in result['data']:
        s_lst.append(" ".join([str(s['id']), s['name'], str(s['group'])]))
    s_str = '\n'.join(s_lst)
    update.message.reply_text(s_str)


def employees_list():
    employees_lst = remonline_api_get('employees/')['data']
    employees_dict = {}
    for e in employees_lst:
        employees_dict[e['id']] = e
    return employees_dict


def check_params():

    global TG_CHAT_LST
    global EMPLOYEES

    if TG_TOKEN == "":
        logger.error("You must specify TG_TOKEN environment variable")
        exit(0)

    if TG_CHAT_IDS == "":
        logger.error("You must specify TG_CHAT_IDS environment variable")
        exit(0)

    try:
        TG_CHAT_LST = map(str.strip, TG_CHAT_IDS.split(','))
        TG_CHAT_LST = [int(x) for x in TG_CHAT_LST]
        logger.debug("Allowed chat_ids: '%s'", TG_CHAT_LST)
    except:
        logger.error("Error on cast TG_CHAT_IDS to list of int")
        exit(0)

    if API_KEY == "":
        logger.error("You must specify API_KEY environment variable")
        exit(0)

    EMPLOYEES = employees_list()
    logger.debug("EMPLOYEES: '%s'", EMPLOYEES)


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TG_TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("get_orders", get_orders, filters=(Filters.chat(TG_CHAT_LST))))
    dp.add_handler(CommandHandler("go", get_orders, filters=(Filters.chat(TG_CHAT_LST))))
    dp.add_handler(CommandHandler("clients", client_list, filters=(Filters.chat(TG_CHAT_LST))))
    dp.add_handler(CommandHandler("cl", client_list, filters=Filters.chat(chat_id=TG_CHAT_LST)))
    dp.add_handler(CommandHandler("statuses", status_list, filters=(Filters.chat(TG_CHAT_LST))))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    check_params()
    main()
