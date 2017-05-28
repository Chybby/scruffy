from __future__ import (
    absolute_import,
    print_function,
)

import hmac
import json
import requests
import random
from time import sleep

from flask import (
    Flask,
    g,
    make_response,
    request,
)

from redis import StrictRedis
from wit import Wit

from config import (
    APP_SECRET,
    REDIS_PORT,
    VERIFY_TOKEN,
    PAGE_ACCESS_TOKEN,
    WITAI_ACCESS_TOKEN,
)


app = Flask(__name__)
app.config.from_object('config')

PAYLOAD_DONE = 'DONE'
PAYLOAD_PASS = 'PASS'
PAYLOAD_REMIND = 'REMIND'
PAYLOAD_FORGOT = 'FORGOT'

REDIS_ROSTER = 'roster'
REDIS_PASSERS = 'passers'
REDIS_REMIND = 'remind'
REDIS_LAST_MESSAGED = 'last_messaged'

FACTS = [
    'Recycling one aluminium can saves enough energy to run a TV for three hours - or the equivalent of 2 litres of petrol.',
    'On average, a baby will go through 6000 disposable diapers before they are potty trained.',
    'Motor oil never wears out, it just gets dirty. Old oil can be recycled, re-refined and used again.',
    'Every year we make enough plastic film to shrink-wrap the state of Texas.',
    'There is a nonprofit company in Japan that recycles old dentures and donates the proceeds to UNICEF.',
    'During World War 1, enough metal was salvaged from corset stays to build two warships.',
    'It takes 80-100 years for an aluminum can to decompose in a landfill.',
    'Glass takes over 1,000,000 (one million) years to decompose in a landfill.',
    'Old crayons don\'t decompose but you can send your unused colors into Crazy Crayons to have them recycled into new!',
    'It takes a 15-year-old tree to produce 700 grocery bags.',
    'Recycling aluminium cans saves 95%% of the energy used to make new cans.',
    'Used condoms were recycled into hair bands in Southern China. They sold quite well, although several physicians voiced concerns about potential hygiene problems.',
    'Burying coffins also means that 90,272 tons of steel, 2,700 tons of copper and bronze, and over 30 million feet of hard wood covered in toxic laminates are also buried per year.',
    'Before the twentieth century, most Americans and Europeans practiced habits of reuse and recycling that prevailed in agricultural communities. For example, in the Middle Ages, tanners would often collect urine to use in tanning animal skins or making gunpowder.',
    'Bones were often recycled into common household items such as buttons, glue, and paper.',
]

###
#
# Wit.ai functions
#
###

def wit_send(request, response):
    user_id = request['session_id'].split('_')[0]
    send_text_message(user_id, response['text'])


def wit_done(request):
    user_id = request['session_id'].split('_')[0]
    if get_last_messaged() == user_id:
        mark_as_done()
        return {'success': 1}

    return {'not_your_turn': 1}


def wit_pass(request):
    user_id = request['session_id'].split('_')[0]
    if get_last_messaged() == user_id:
        was_passed = mark_as_passed()
        if was_passed:
            return {'users_left': 1}
        else:
            return {'everyone_passed': 1}

    return {'not_your_turn': 1}


def wit_remind(request):
    user_id = request['session_id'].split('_')[0]
    if get_last_messaged() == user_id:
        # TODO: don't do this if it is past 8
        set_remind()
        return {'success': 1}

    return {'not_your_turn': 1}


def wit_next(request):
    return {'next': get_info(get_roster()[0])['first_name']}


def wit_roster(request):
    named_roster = map(lambda x: get_info(x)['first_name'], get_roster())
    string_roster = ', '.join(named_roster)
    return {'roster': string_roster}


def wit_notify(request):
    send_notification()
    return {}


def wit_add_new(request):
    user_id = request['session_id'].split('_')[0]
    was_added = add_to_roster(user_id)
    if was_added:
        return {'new': 1}
    else:
        return {'existing': 1}


def wit_fact(request):
    return {'fact': get_bin_fact()}


def get_wit():
    wit_client = getattr(g, '_wit_client', None)
    if wit_client is None:
        actions = {
            'send': wit_send,
            'done': wit_done,
            'pass': wit_pass,
            'remind': wit_remind,
            'next': wit_next,
            'roster': wit_roster,
            'notify': wit_notify,
            'add_new': wit_add_new,
            'fact': wit_fact,
        }

        wit_client = g._wit_client = Wit(access_token=WITAI_ACCESS_TOKEN,
                                         actions=actions)
    return wit_client

###
#
# Redis Functions
#
###

def get_redis():
    redis = getattr(g, '_redis', None)
    if redis is None:
        redis = g._redis = StrictRedis(host='localhost', port=REDIS_PORT, db=0)
    return redis


def get_roster():
    return get_redis().lrange(REDIS_ROSTER, 0, -1)


def add_to_roster(user_id):
    class FnScope:
        was_added = False
    def _add_to_roster(pipe):
        roster = pipe.lrange(REDIS_ROSTER, 0, -1)
        if user_id not in roster:
            pipe.rpush(REDIS_ROSTER, user_id)
            FnScope.was_added = True

    get_redis().transaction(_add_to_roster, REDIS_ROSTER)

    return FnScope.was_added


def get_passers():
    return get_redis().lrange(REDIS_PASSERS, 0, -1)


def get_last_messaged():
    return get_redis().get(REDIS_LAST_MESSAGED)


def get_info_from_redis(user_id):
    return get_redis().get(user_id + 'info')


def set_info_in_redis(user_id, info):
    get_redis().set(user_id + 'info', info)


def set_remind():
    with get_redis().pipeline() as pipe:
        pipe.set(REDIS_REMIND, True)
        pipe.execute()


def mark_as_done():
    def _mark_as_done(pipe):
        done_id = pipe.lindex(REDIS_ROSTER, 0)
        pipe.multi()
        pipe.lpop(REDIS_ROSTER)
        pipe.rpush(REDIS_ROSTER, done_id)
        pipe.ltrim(REDIS_PASSERS, 1, 0)
        pipe.set(REDIS_LAST_MESSAGED, None)
        pipe.set(REDIS_REMIND, False)

    get_redis().transaction(_mark_as_done, REDIS_ROSTER)


def mark_as_passed():
    class FnScope:
        was_passed = True
    def _mark_as_passed(pipe):
        passer_id = pipe.lindex(REDIS_ROSTER, 0)
        passers = pipe.lrange(REDIS_PASSERS, 0, -1)
        if pipe.llen(REDIS_ROSTER) - 1 == len(passers):
            # Everyone has passed
            pipe.multi()
            pipe.lpop(REDIS_ROSTER)
            pipe.rpush(REDIS_ROSTER, passer_id)
            pipe.ltrim(REDIS_PASSERS, 1, 0)
            FnScope.was_passed = False
        else:
            next_id = pipe.lindex(REDIS_ROSTER, len(passers) + 1)
            pipe.multi()
            passers.append(passer_id)
            for i in xrange(len(passers) + 1):
                pipe.lpop(REDIS_ROSTER)
            pipe.rpush(REDIS_PASSERS, passer_id)
            for i in xrange(len(passers) - 1, -1, -1):
                pipe.lpush(REDIS_ROSTER, passers[i])
            pipe.lpush(REDIS_ROSTER, next_id)
        pipe.set(REDIS_LAST_MESSAGED, None)
        pipe.set(REDIS_REMIND, False)

    get_redis().transaction(_mark_as_passed, REDIS_ROSTER, REDIS_PASSERS)
    return FnScope.was_passed

###
#
# Util Functions
#
###

def get_info(user_id):
    info = get_info_from_redis(user_id)
    if info:
        return json.loads(info)

    rs = requests.get('https://graph.facebook.com/v2.8/%s?access_token=%s' %
                      (user_id, PAGE_ACCESS_TOKEN))
    info = rs.json()
    set_info_in_redis(user_id, json.dumps(info))
    return info


def create_insult(passers):
    if not passers:
        return ''

    users = passers[:]
    names = []
    while users:
        user = users.pop()
        fist_name = get_info(user)['first_name']
        if len(users) == 0:
            names.append(fist_name)
        elif len(users) == 1:
            names.append(fist_name)
            names.append('and')
        else:
            names.append(fist_name + ',')

    if len(names) == 1:
        return names[0] + ' is being a fuck'

    return ' '.join(names) + ' are being fucks'


def get_bin_fact():
    return random.choice(FACTS)

###
#
# Cron Functions
#
###

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
        send_bin_notification(FnScope.user_id, reminder=True)


def send_notification():
    class FnScope:
        was_naughty = False
        user_id = None
    def _send_notification(pipe):
        FnScope.user_id = pipe.lindex(REDIS_ROSTER, 0)
        if FnScope.user_id == pipe.get(REDIS_LAST_MESSAGED):
            FnScope.was_naughty = True
        pipe.multi()
        pipe.set(REDIS_LAST_MESSAGED, FnScope.user_id)

    get_redis().transaction(_send_notification, REDIS_ROSTER,
                                                REDIS_LAST_MESSAGED)
    if FnScope.was_naughty:
        send_naughty_notification(FnScope.user_id)
    else:
        send_bin_notification(FnScope.user_id)

###
#
# Messenger Functions
#
###

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


def send_bin_notification(recipient_id, reminder=False):
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

    if not reminder:
        message_data['message']['quick_replies'].append({
            'content_type': 'text',
            'title': 'Remind me later',
            'payload': PAYLOAD_REMIND,
        })
        passers = get_passers()
        if passers:
            message_data['message']['text'] = (create_insult(passers) +
            ', so it\'s your turn to empty me today.')

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


def process_message(message):
    sender_id = message['sender']['id']
    time_of_message = int(message['timestamp'])
    message_text = message['message'].get('text')
    message_sticker_id = message['message'].get('sticker_id')

    session_id = "%s_%d" % (sender_id, random.randint(1000000000, 9999999999))

    if message_text:
        get_wit().run_actions(session_id, message_text, {})
    elif message_sticker_id == 369239263222822:
        # thumbs up sticker
        get_wit().run_actions(session_id, '(y)', {})


def verify(data, header, app_secret_key):
    """
    This function will verify the integrity and authenticity of the data received

    :param data: data received from facebook
    :param header: headers of the request
    :param app_secret_key: facebook app secret key. You can find it on your app page
    :return: True if signature matches else returns false

    """
    X_hub_sign = header["X-Hub-Signature"]
    method, sign = X_hub_sign.split("=")
    """
    Now a key will be created of data using app secret as the key.
    And compared with xsignature found in the the headers of the request.
    If both the keys match then the function will run further otherwise it will halt
    """
    hmac_object = hmac.new(app_secret_key.encode("utf-8"), data, "sha1")
    key = hmac_object.hexdigest()
    return hmac.compare_digest(sign, key)

###
#
# Flask Routes
#
###

@app.route('/')
def index():
    # Show web ui
    return 'There\'ll be a web ui here someday maybe'


@app.route('/webhook', methods=['POST'])
def receive_message():
    header = request.headers
    data = request.get_data()
    if not verify(data, header, APP_SECRET):
        return ''

    data = request.get_json()
    if (data['object'] == 'page'):
        for entry in data['entry']:
            page_id = entry['id']
            time_of_event = entry['time']

            for message in entry['messaging']:
                if 'message' in message:
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
