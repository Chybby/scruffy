from __future__ import (
    absolute_import,
    print_function,
)

import json
import requests
from time import sleep

from flask import (
    Flask,
    g,
    make_response,
    request,
)

from redis import StrictRedis

from config import (
    REDIS_PORT,
    VERIFY_TOKEN,
    PAGE_ACCESS_TOKEN,
)


app = Flask(__name__)
app.config.from_object('config')

PAYLOAD_DONE = 'DONE'
PAYLOAD_PASS = 'PASS'
PAYLOAD_REMIND = 'REMIND'
PAYLOAD_FORGOT = 'FORGOT'

REDIS_ROSTER = 'roster'
REDIS_PASSERS = 'passers'
REDIS_BINS_DONE = 'bins_done'
REDIS_REMIND = 'remind'
REDIS_LAST_MESSAGED = 'last_messaged'


def get_redis():
    redis = getattr(g, '_redis', None)
    if redis is None:
        redis = g._redis = StrictRedis(host='localhost', port=REDIS_PORT, db=0)
    return redis


def add_to_roster(user_id):
    class FnScope:
        was_added = False
    def _add_to_roster(pipe):
        roster = pipe.lrange(REDIS_ROSTER, 0, -1)
        if user_id not in roster:
            if roster:
                roster_head = pipe.lindex(REDIS_ROSTER, 0)
            pipe.multi()
            pipe.lpop(REDIS_ROSTER)
            pipe.lpush(REDIS_ROSTER, user_id)
            if roster:
                pipe.lpush(REDIS_ROSTER, roster_head)
            FnScope.was_added = True

    get_redis().transaction(_add_to_roster, REDIS_ROSTER)

    return FnScope.was_added


def get_last_messaged():
    return get_redis().get(REDIS_LAST_MESSAGED)


def set_remind():
    with get_redis().pipeline() as pipe:
        pipe.set(REDIS_REMIND, True)
        pipe.set(REDIS_LAST_MESSAGED, None)

def send_reminder():
    class FnScope:
        needs_reminding = False
        user_id = None
    def _send_reminder(pipe):
        FnScope.needs_reminding = pipe.get(REDIS_REMIND) == 'True'
        if FnScope.needs_reminding:
            FnScope.user_id = pipe.lindex(REDIS_ROSTER, 0)
            pipe.multi()
            pipe.set(REDIS_LAST_MESSAGED, FnScope.user_id)
            pipe.set(REDIS_REMIND, False)

    get_redis().transaction(_send_reminder, REDIS_REMIND, REDIS_ROSTER)
    if FnScope.needs_reminding:
        send_bin_notification(FnScope.user_id, reminder=False)

def send_notification():
    class FnScope:
        was_naughty = False
        user_id = None
    def _send_notification(pipe):
        FnScope.user_id = pipe.lindex(REDIS_ROSTER, 0)
        bins_done = pipe.get(REDIS_BINS_DONE) == 'True'
        if not bins_done:
            FnScope.was_naughty = True
        pipe.multi()
        pipe.set(REDIS_LAST_MESSAGED, FnScope.user_id)
        pipe.set(REDIS_BINS_DONE, False)

    get_redis().transaction(_send_notification, REDIS_ROSTER, REDIS_BINS_DONE)
    if FnScope.was_naughty:
        send_naughty_notification(FnScope.user_id)
    else:
        send_bin_notification(FnScope.user_id)

def mark_as_done():
    def _mark_as_done(pipe):
        done_id = pipe.lindex(REDIS_ROSTER, 0)
        pipe.multi()
        pipe.lpop(REDIS_ROSTER)
        pipe.rpush(REDIS_ROSTER, done_id)
        pipe.set(REDIS_BINS_DONE, True)
        pipe.ltrim(REDIS_PASSERS, 1, 0)
        pipe.set(REDIS_LAST_MESSAGED, None)

    get_redis().transaction(_mark_as_done, REDIS_ROSTER)

def mark_as_forgot_done():
    class FnScope:
        next_id = None

    def _mark_as_forgot_done(pipe):
        done_id = pipe.lindex(REDIS_ROSTER, 0)
        FnScope.next_id = pipe.lindex(REDIS_ROSTER, 1)
        pipe.multi()
        pipe.lpop(REDIS_ROSTER, 0)
        pipe.rpush(REDIS_ROSTER, done_id)
        pipe.set(REDIS_LAST_MESSAGED, FnScope.next_id)
        pipe.ltrim(REDIS_PASSERS, 1, 0)

    get_redis().transaction(_mark_as_forgot_done, REDIS_ROSTER)
    return FnScope.next_id


def mark_as_passed():
    class FnScope:
        was_passed = True
        next_id = None
        passers = []
    def _mark_as_passed(pipe):
        passer_id = pipe.lindex(REDIS_ROSTER, 0)
        FnScope.passers = pipe.lrange(REDIS_PASSERS, 0, -1)
        if pipe.llen(REDIS_ROSTER) - 1 == len(FnScope.passers):
            # Everyone has passed
            pipe.multi()
            pipe.lpop(REDIS_ROSTER)
            FnScope.passers.append(passer_id)
            for i in xrange(len(FnScope.passers) - 1, -1, -1):
                pipe.lpush(REDIS_ROSTER, FnScope.passers[i])
            pipe.ltrim(REDIS_PASSERS, 1, 0)
            # Avoid berating the next person for not emptying the bin
            pipe.set(REDIS_BINS_DONE, True)
            FnScope.was_passed = False
        else:
            FnScope.next_id = pipe.lindex(REDIS_ROSTER, len(FnScope.passers) + 1)
            pipe.multi()
            for i in xrange(len(FnScope.passers) + 1):
                pipe.lpop(REDIS_ROSTER)
            pipe.rpush(REDIS_PASSERS, passer_id)
            FnScope.passers.append(passer_id)
            for i in xrange(len(FnScope.passers) - 1, -1, -1):
                pipe.lpush(REDIS_ROSTER, FnScope.passers[i])
            pipe.lpush(REDIS_ROSTER, FnScope.next_id)
            pipe.set(REDIS_LAST_MESSAGED, FnScope.next_id)

    get_redis().transaction(_mark_as_passed, REDIS_ROSTER, REDIS_PASSERS)
    return (FnScope.was_passed, FnScope.next_id, FnScope.passers)


def call_send_API(message_data):
    rs = requests.post('https://graph.facebook.com/v2.6/me/messages',
                       params={'access_token': PAGE_ACCESS_TOKEN},
                       json=message_data)

    if rs.status_code != requests.codes.ok:
        print('Couldn\'t send message, got status %d' % rs.status_code)
        print(rs.text)


def send_naughty_notification(recipient_id):
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': 'You didn\'t empty me when I told you to! Do it today please',
            'quick_replies': [
                {
                    'content_type': 'text',
                    'title': 'Ok, done',
                    'payload': PAYLOAD_DONE,
                },
                {
                    'content_type': 'text',
                    'title': 'I can\'t today',
                    'payload': PAYLOAD_PASS,
                },
                {
                    'content_type': 'text',
                    'title': 'Remind me later',
                    'payload': PAYLOAD_REMIND,
                },
                {
                    'content_type': 'text',
                    'title': 'I forgot to say done',
                    'payload': PAYLOAD_FORGOT,
                },
            ]
        }
    }

    call_send_API(message_data)


def send_bin_notification(recipient_id, passers=[], reminder=True):
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': 'It\'s your turn to empty me today!',
            'quick_replies': [
                {
                    'content_type': 'text',
                    'title': 'Ok, done',
                    'payload': PAYLOAD_DONE,
                },
                {
                    'content_type': 'text',
                    'title': 'I can\'t today',
                    'payload': PAYLOAD_PASS,
                },
            ]
        }
    }

    if reminder:
        message_data['message']['quick_replies'].append({
            'content_type': 'text',
            'title': 'Remind me later',
            'payload': PAYLOAD_REMIND,
        })

    call_send_API(message_data)


def send_text_message(recipient_id, text):
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': text
        }
    }

    call_send_API(message_data)


def process_quick_reply(message):
    sender_id = message['sender']['id']
    time_of_message = int(message['timestamp'])

    if sender_id != get_last_messaged():
        # Someone is trying to send a quick reply when they shouldn't be able to
        send_text_message(sender_id, "Stop trying to break me :(")
        return

    payload = message['message']['quick_reply']['payload']

    if payload == PAYLOAD_DONE:
        mark_as_done()
        send_text_message(sender_id, 'Thanks buddy, I feel so refreshed')
    elif payload == PAYLOAD_PASS:
        was_passed, next_id, passers = mark_as_passed()
        if not was_passed:
            send_text_message(sender_id, 'Guess I\'m staying full today :(')
        else:
            send_text_message(sender_id, 'Ok, I\'ll ask someone else to empty me')
            send_bin_notification(next_id, passers=passers)
    elif payload == PAYLOAD_REMIND:
        # TODO: don't do this if it's past 8pm
        set_remind()
        send_text_message(sender_id, 'Ok, I\'ll remind you this evening')
    elif payload == PAYLOAD_FORGOT:
        next_id = mark_as_forgot_done()
        send_text_message(sender_id, 'All good, I\'ll ask someone else then')
        send_bin_notification(next_id)


def process_message(message):
    sender_id = message['sender']['id']
    time_of_message = int(message['timestamp'])
    message_text = message['message'].get('text')

    if add_to_roster(sender_id):
        send_text_message(sender_id, 'The world could always use more bin emptiers')
    else:
        send_text_message(sender_id, 'Don\'t you have something better to do than talking to a bin?')

@app.route('/')
def index():
    # Show web ui
    return 'There\'ll be a web ui here someday maybe'


@app.route('/webhook', methods=['POST'])
def receive_message():
    data = request.get_json()
    if (data['object'] == 'page'):
        for entry in data['entry']:
            page_id = entry['id']
            time_of_event = entry['time']

            for message in entry['messaging']:
                if 'message' in message:
                    if 'quick_reply' in message['message']:
                        process_quick_reply(message)
                    else:
                        process_message(message)

    return ''


@app.route('/webhook', methods=['GET'])
def validate_webhook():
    if (request.args['hub.mode'] == 'subscribe' and
        request.args['hub.verify_token'] == VERIFY_TOKEN):
        # Validating webhook
        return request.args['hub.challenge']

    abort(403)


if __name__ == '__main__':
    app.run()
