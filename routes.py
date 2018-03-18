from __future__ import print_function

from config import VERIFY_TOKEN
from cron import check_bins_done, send_notification, send_reminder
from flask import Blueprint, abort, request
from process_messages import process_messages

routes = Blueprint('routes', __name__)


@routes.route('/')
def index_route():
    # Show web ui
    return 'There\'ll be a web ui here someday maybe'


@routes.route('/webhook', methods=['POST'])
def receive_message_route():
    return process_messages(request)


@routes.route('/webhook', methods=['GET'])
def validate_webhook_route():
    if (request.args['hub.mode'] == 'subscribe' and
            request.args['hub.verify_token'] == VERIFY_TOKEN):
        # Validating webhook
        return request.args['hub.challenge']

    abort(403)


@routes.route('/send_notification', methods=['GET'])
def send_notification_route():
    send_notification()
    return ''


@routes.route('/check_bins_done', methods=['GET'])
def check_bins_done_route():
    check_bins_done()
    return ''


@routes.route('/send_reminder', methods=['GET'])
def send_reminder_route():
    send_reminder()
    return ''
