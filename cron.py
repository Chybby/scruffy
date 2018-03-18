from __future__ import print_function

from models import Roster
from send_messages import send_bin_notification, send_naughty_notification


def send_notification():
    result, user_key = Roster.send_notification()
    if result == Roster.NORMAL_NOTIFICATION:
        send_bin_notification(user_key.id(), passers=Roster.get_passers())
    elif result == Roster.NAUGHTY_NOTIFICATION:
        send_naughty_notification(user_key.id())


def check_bins_done():
    if Roster.get_bins_done():
        return
    if Roster.should_send_reminder():
        return
    send_naughty_notification(Roster.get_next().fbid)


def send_reminder():
    user_key = Roster.send_reminder()
    if user_key is None:
        return

    send_bin_notification(user_key.id(), reminder=True)
