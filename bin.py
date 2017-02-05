from __future__ import (
    absolute_import,
    print_function,
)

import json
import requests

from flask import (
    Flask,
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


def get_redis():
    redis = getattr(g, '_redis', None)
    if redis is None:
        redis = g._redis = StrictRedis(host='localhost', port=REDIS_PORT, db=0)
    return redis


def call_send_API(message_data):
    rs = requests.post('https://graph.facebook.com/v2.6/me/messages',
                       params={'access_token': PAGE_ACCESS_TOKEN},
                       json=message_data)

    if rs.status_code == requests.codes.ok:
        data = rs.json()
        recipient_id = int(data['recipient_id'])
        message_id = data['message_id']
        print('Successfully sent message to %d with id %s' % (recipient_id,
                                                              message_id))
    else:
        print('Unsuccessfully sent message (%d)', rs.status_code)


def send_bin_notification(recipient_id):
    message_data = {
        'recipient': {
            'id': recipient_id
        },
        'message': {
            'text': 'It\'s your turn to take the bins out today!',
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
            ]
        }
    }

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
    sender_id = int(message['sender']['id'])
    time_of_message = int(message['timestamp'])

    payload = message['message']['quick_reply']['payload']

    if payload == PAYLOAD_DONE:
        send_text_message(sender_id, 'Thanks buddy')
    elif payload == PAYLOAD_PASS:
        send_text_message(sender_id, 'Someone else will have to do it today')
    elif payload == PAYLOAD_REMIND:
        send_text_message(sender_id, 'Ok, I\'ll remind you this evening')


def process_message(message):
    sender_id = int(message['sender']['id'])
    time_of_message = int(message['timestamp'])
    message_text = message['message'].get('text')

    send_text_message(sender_id, 'FYI: bot ain\'t ready yet')
    send_bin_notification(sender_id)


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
