#!/usr/bin/env python
# -*- coding: utf-8 -*-


from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode

import logging
import os
import requests
import re


TG_TOKEN = os.getenv('TG_TOKEN', "")
TG_CHAT_IDS = os.getenv('TG_CHAT_IDS', "")
TG_CHAT_LST = []
TG_CHAT_NOTICE_IDS = os.getenv('TG_CHAT_NOTICE_IDS', "")
TG_CHAT_NOTICE_LST = []

API_KEY = os.getenv('API_KEY', "")
API_TOKEN = '' # empty at start
API_BASE_URL = "https://api.remonline.ru/"
API_MAX_RETRIES = 5
API_POLL_INTERVAL_SEC = 15
API_REC_PER_PAGE = 50

TRACK_DICT = {}


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
        res = r.json()
        if 'page' in res and 'count' in res:
            if int(res['count']) > int(res['page']) * API_REC_PER_PAGE:
                res['data'] += remonline_api_get(api_path, token, filters, page + 1, retries)['data']
        return res

    elif r.status_code == 403:
        new_token = remonline_api_renew_token()
        if new_token:
            return remonline_api_get(api_path, new_token, filters, page, retries + 1)

    return None


def chat_id(bot, update):
    """Send this chat_id in reply """
    update.message.reply_text(update.message.chat_id)


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def order_sting_helper(o, detailed_flag=False):

    if 'engineer_id' in o:
        e_id = o['engineer_id']
    else:
        e_id = None
    if detailed_flag:
        ret = "*{}* {} ({}) *{}*\n*model*: `{}`\n*malfunction*: `{}`\n*manager_notes*: `{}`\n*engineer_notes*: `{}`".format(
            o['id_label'],
            o['client']['name'],
            o['status']['name'],
            engineer_name_helper(e_id),
            o['model'],
            o['malfunction'],
            o['manager_notes'],
            o['engineer_notes'])
    else:
        ret = "*{}* {} ({}) *{}*".format(o['id_label'], o['client']['name'],
                                     o['status']['name'], engineer_name_helper(e_id))

    return ret


def engineer_name_helper(engineer_id):
    if engineer_id in EMPLOYEES:
        engineer = EMPLOYEES[engineer_id]['first_name'] + ' ' + EMPLOYEES[engineer_id]['last_name']
    else:
        engineer = '=FREE='

    return engineer


def compare_orders(current_order_list):
    """ compare two lists of orders, change state and return notice text for channel """
    global TRACK_DICT
    ret = []

    for o in current_order_list:

        if 'engineer_id' in o:
            e_id = o['engineer_id']
        else:
            e_id = None

        if o['id_label'] in TRACK_DICT['orders']:
            if TRACK_DICT['orders'][o['id_label']]['status'] != o['status']['name']:
                ret.append("Status was changed: {}".format(order_sting_helper(o)))
            if TRACK_DICT['orders'][o['id_label']]['engineer'] != engineer_name_helper(e_id):
                ret.append("Engineer was changed: {}".format(order_sting_helper(o)))
        else:
            ret.append("New order: {}".format(order_sting_helper(o)))

        TRACK_DICT['orders'][o['id_label']] = {'status': o['status']['name'],
                                               'engineer': engineer_name_helper(e_id)}
    return '\n'.join(ret)


def poll_orders():
    """ track orders on periodic manner """
    global TRACK_DICT

    filters = {}
    result = remonline_api_get('order/', filters=filters)

    if 'orders' not in TRACK_DICT:
        # just started - no tracking orders. Fill-up and silently wait for changes

        TRACK_DICT['orders'] = {}

        for o in result['data']:

            if 'engineer_id' in o:
                e_id = o['engineer_id']
            else:
                e_id = None

            TRACK_DICT['orders'][o['id_label']] = {'status': o['status']['name'],
                                                   'engineer': engineer_name_helper(e_id)}

        logging.debug("First time tracking. Fill-up and silently wait for changes. Tracking dict for orders: '%s'",
                      TRACK_DICT['orders'])
        return None

    else:
        logging.debug("Order tracking loop with non-zero tracking dict")
        return compare_orders(result['data'])


def get_orders(bot, update, args):
    """ Get orders from external system """

    filters = {}
    orders_detailed = False

    if len(args) > 0:
        filters = {'id_labels[]': args[0]}
        orders_detailed = True

    result = remonline_api_get('order/', filters=filters)
    orders_lst = []
    for o in result['data']:
        if o['status']['group'] in [6, 7]:
            # we don't need closed and canceled orders
            continue

        orders_lst.append(order_sting_helper(o, orders_detailed))

    orders_str = '\n'.join(orders_lst)
    update.message.reply_markdown(orders_str, quote=False)


def client_list(bot, update):
    """ Get client list from external system """
    result = remonline_api_get('clients/')
    client_lst = []
    for cl in result['data']:
        client_lst.append(cl['name'])
    clients_str = '\n'.join(client_lst)
    update.message.reply_text(clients_str, quote=False)


def status_list(bot, update):
    """ Get status list from external system """
    result = remonline_api_get('statuses/')
    s_lst = []
    for s in result['data']:
        s_lst.append(" ".join([str(s['id']), s['name'], str(s['group'])]))
    s_str = '\n'.join(s_lst)
    update.message.reply_text(s_str, quote=False)


def employees_list():
    employees_lst = remonline_api_get('employees/')['data']
    employees_dict = {}
    for e in employees_lst:
        m = re.search('tg:(\S+)', e['notes'])
        if m:
            e['tg_handle'] = m.group(1)
        employees_dict[e['id']] = e
    return employees_dict


def poll_api(bot, job):

    notice = poll_orders()

    if notice:
        for c in TG_CHAT_NOTICE_LST:
            bot.send_message(chat_id=c, text=notice, parse_mode=ParseMode.MARKDOWN)
            logger.debug("Notice to chat '%s' send with text '%s'", c, notice)


def check_params():

    global TG_CHAT_LST
    global TG_CHAT_NOTICE_LST
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

    if TG_CHAT_NOTICE_IDS != "":
        try:
            TG_CHAT_NOTICE_LST = map(str.strip, TG_CHAT_NOTICE_IDS.split(','))
            TG_CHAT_NOTICE_LST = [int(x) for x in TG_CHAT_NOTICE_LST]
            logger.debug("Chats for poll notice: '%s'", TG_CHAT_NOTICE_LST)
        except:
            logger.error("Error on cast TG_CHAT_NOTICE_LST to list of int")
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
    dp.add_handler(CommandHandler("chat_id", chat_id))
    dp.add_handler(CommandHandler(["get_orders", "go"], get_orders, filters=(Filters.chat(TG_CHAT_LST)),
                                  pass_args=True))
    dp.add_handler(CommandHandler(["clients", "cl"], client_list, filters=(Filters.chat(TG_CHAT_LST))))
    dp.add_handler(CommandHandler("statuses", status_list, filters=(Filters.chat(TG_CHAT_LST))))

    if TG_CHAT_NOTICE_LST:
        j = updater.job_queue
        job_minute = j.run_repeating(poll_api, interval=API_POLL_INTERVAL_SEC, first=0)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling(timeout=60)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    check_params()
    main()
