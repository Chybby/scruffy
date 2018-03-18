from __future__ import print_function

import logging

import requests
from config import PAGE_ACCESS_TOKEN
from facts import get_bin_fact
from google.appengine.ext import ndb
from intents import (
    DONE_INTENT,
    FACT_INTENT,
    FORGOT_INTENT,
    GREET_INTENT,
    NEXT_INTENT,
    PASS_INTENT,
    REMIND_INTENT,
    ROSTER_INTENT,
    THANKS_INTENT,
)
from models import Roster, User
from send_messages import (
    send_bin_notification,
    send_naughty_notification,
    send_text_message,
)


def do_action_for_entities(fbid, entities):
    logging.info(entities)
    intent = entities.get('intent')
    if not intent:
        # No intent found, do nothing
        return
    intent_value = intent[0].get('value')
    logging.info('Found intent value "%s"' % intent_value)

    user = User.get(fbid)

    if user is None:
        if intent_value == GREET_INTENT:
            user = _register_new_user(fbid)
            send_text_message(fbid, 'Hi! I\'ve put you on the roster.')
        else:
            send_text_message(fbid, 'I don\'t know you! Try saying hello first')
        return

    if intent_value == GREET_INTENT:
        send_text_message(fbid, 'Hi :)')
    elif intent_value == DONE_INTENT:
        action_done(user)
    elif intent_value == PASS_INTENT:
        action_pass(user)
    elif intent_value == REMIND_INTENT:
        action_remind(user)
    elif intent_value == FORGOT_INTENT:
        action_forgot(user)
    elif intent_value == NEXT_INTENT:
        action_next(user)
    elif intent_value == ROSTER_INTENT:
        action_roster(user)
    elif intent_value == FACT_INTENT:
        action_fact(user)
    elif intent_value == THANKS_INTENT:
        action_thanks(user)
    else:
        logging.error('Unexpected intent value')


def _register_new_user(fbid):
    rs = requests.get('https://graph.facebook.com/v2.12/%s?access_token=%s' %
                      (fbid, PAGE_ACCESS_TOKEN))
    info = rs.json()
    logging.info(info)
    name = info['first_name'] + ' ' + info['last_name']

    user = User.create(fbid, name)

    Roster.register_new_user(user)

    return user


def action_done(user):
    result = Roster.set_done(user)

    if result == Roster.SUCCESS:
        send_text_message(user.fbid, 'Thanks, I feel so refreshed!')
    else:
        send_text_message(user.fbid, 'It\'s not your turn.')


def action_forgot(user):
    result = Roster.set_done(user)

    if result == Roster.SUCCESS:
        send_text_message(user.fbid, 'I\'ll let you off the hook... this time.')
    else:
        send_text_message(user.fbid, 'It\'s not your turn.')


def action_pass(user):
    result = Roster.set_passed(user)
    if result == Roster.SUCCESS:
        send_text_message(user.fbid, 'Ok, I\'ll ask someone else to empty me.')
        send_bin_notification(Roster.get_next().fbid, Roster.get_passers())
    elif result == Roster.EVERYONE_PASSED:
        send_text_message(user.fbid, 'Guess I\'m staying full today :(')
    else:
        send_text_message(user.fbid, 'It\'s not your turn.')


def action_remind(user):
    result = Roster.set_remind(user)
    if result == Roster.SUCCESS:
        send_text_message(user.fbid, 'I\'ll remind you tomorrow morning.')
    else:
        send_text_message(user.fbid, 'It\'s not your turn.')


def action_next(user):
    send_text_message(user.fbid, Roster.get_next().name + ' is next.')


def action_roster(user):
    named_roster = [u.name for u in Roster.get_queue()]
    string_roster = ', '.join(named_roster)
    send_text_message(user.fbid, 'Here\'s the roster: ' + string_roster)


def action_fact(user):
    send_text_message(user.fbid, get_bin_fact())


def action_thanks(user):
    send_text_message(user.fbid, 'No, thank you for being such a responsible'
                      ' housemate :)')
