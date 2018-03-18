from __future__ import print_function

import logging

import requests
from config import PAGE_ACCESS_TOKEN
from intents import DONE_INTENT, FORGOT_INTENT, PASS_INTENT, REMIND_INTENT


def send_naughty_notification(recipient_id):
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': ('You didn\'t empty me when I '
                     'told you to! Do it today please.'),
            'quick_replies': [
                {
                    'content_type': 'text',
                    'title': 'Ok, done',
                    'payload': DONE_INTENT,
                },
                {
                    'content_type': 'text',
                    'title': 'I can\'t today',
                    'payload': PASS_INTENT,
                },
                {
                    'content_type': 'text',
                    'title': 'Remind me later',
                    'payload': REMIND_INTENT,
                },
                {
                    'content_type': 'text',
                    'title': 'I forgot to say done',
                    'payload': FORGOT_INTENT,
                },
            ]
        }
    }

    _send_message(message_data)


def send_bin_notification(recipient_id, passers=None, reminder=False):
    text = 'It\'s your turn to empty me today!'
    if passers:
        text = (_create_insult(passers) + ', so it\'s your turn to empty me'
                ' today!')
    if reminder:
        text = 'Remember to take the bins out today.'

    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': text,
            'quick_replies': [
                {
                    'content_type': 'text',
                    'title': 'Ok, done',
                    'payload': DONE_INTENT,
                },
                {
                    'content_type': 'text',
                    'title': 'Remind me later',
                    'payload': REMIND_INTENT,
                },
                {
                    'content_type': 'text',
                    'title': 'I can\'t today',
                    'payload': PASS_INTENT,
                }
            ]
        }
    }

    _send_message(message_data)


def send_text_message(recipient_id, text):
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': text
        }
    }

    _send_message(message_data)


def _send_message(message_data):
    rs = requests.post('https://graph.facebook.com/v2.12/me/messages',
                       params={'access_token': PAGE_ACCESS_TOKEN},
                       json=message_data)

    if rs.status_code != requests.codes.ok:
        logging.error('Couldn\'t send message, got status %d' % rs.status_code)
        logging.error(rs.text)


def _create_insult(passers):
    if not passers:
        return ''

    users = passers[:]
    names = []
    while users:
        user = users.pop()
        name = user.name
        if len(users) == 0:
            names.append(name)
        elif len(users) == 1:
            names.append(name)
            names.append('and')
        else:
            names.append(name + ',')

    if len(names) == 1:
        return names[0] + ' is being a fuck'

    return ' '.join(names) + ' are being fucks'
