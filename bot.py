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

API_KEY = os.getenv('API_KEY', "")
API_TOKEN = '' # empty at start
API_BASE_URL = "https://api.remonline.ru/"
API_MAX_RETRIES = 5


HTTP_CLIENT_TIMEOUT = 5

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)

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
    update.message.reply_text(result)


def client_list(bot, update):
    """ Get client list from external system """
    result = remonline_api_get('clients/')
    client_lst = []
    for cl in result['data']:
        client_lst.append(cl['name'])
    clients_str = '\n'.join(client_lst)
    update.message.reply_text(clients_str)


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TG_TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("get_orders", get_orders))
    dp.add_handler(CommandHandler("go", get_orders))
    dp.add_handler(CommandHandler("clients", client_list))
    dp.add_handler(CommandHandler("cl", client_list))

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
    main()