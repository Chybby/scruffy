from __future__ import print_function

import hashlib
import hmac
import logging

from actions import do_action_for_entities
from config import APP_SECRET

SMALL_THUMBS_UP_ID = 369239263222822
MEDIUM_THUMBS_UP_ID = 369239343222814
LARGE_THUMBS_UP_ID = 369239383222810


def process_messages(request):
    headers = request.headers
    data = request.get_data()
    logging.info('Received webhook event:')
    logging.info(headers)
    logging.info(data)

    if not _verify(data, headers, APP_SECRET):
        return 'couldn\'t verify data'

    data = request.get_json()
    if (data['object'] == 'page'):
        for entry in data['entry']:
            page_id = entry['id']
            time_of_event = entry['time']

            for message in entry['messaging']:
                if 'message' in message:
                    _process_message(message)

    return 'processed_messages'


def _verify(data, headers, app_secret_key):
    '''
    Verifies the integrity/authenticity of the received data.

    data: data received from facebook.
    headers: headers of the request.
    app_secret_key: facebook app secret key.

    returns: True if signature matches else returns false.
    '''

    X_hub_sign = headers['X-Hub-Signature']
    method, sign = X_hub_sign.split('=')

    # Now a key will be created of data using app secret as the key.
    # And compared with xsignature found in the the headers of the request.
    # If both the keys match then the message is legitimate.
    hmac_object = hmac.new(app_secret_key.encode('utf-8'), data, hashlib.sha1)
    key = hmac_object.hexdigest()
    return hmac.compare_digest(sign.encode('utf-8'), key)


def _process_message(message):
    sender_id = message['sender']['id']
    message_text = message['message'].get('text')
    message_sticker_id = message['message'].get('sticker_id')
    nlp = message['message'].get('nlp')
    entities = None
    if nlp:
        entities = nlp.get('entities')

    logging.info(message_text + str(entities))

    if message_text and entities is not None:
        do_action_for_entities(sender_id, entities)
    elif message_sticker_id in [SMALL_THUMBS_UP_ID,
                                MEDIUM_THUMBS_UP_ID,
                                LARGE_THUMBS_UP_ID]:
        # thumbs up sticker
        logging.info('Got a thumbs up')
        do_action_for_entities(sender_id, {"intent": [
            {"confidence": 1, "value": "done"}
        ]})
    else:
        logging.error('Message missing necessary fields')
