from __future__ import (
    absolute_import,
    print_function,
)

from config import VERIFY_TOKEN

from flask import (
    Flask,
    request,
)

app = Flask(__name__)
app.config.from_object('config')


@app.route('/')
def index():
    return 'Hello World!'


@app.route('/webhook')
def receive_message(methods=['POST']):
    data = request.get_json()
    print(data)
    if (data['object'] == 'page'):
        print(data['entry'])


app.route('/webhook')
def validate_webhook(methods=['GET']):
    if (request.args['hub.mode'] == 'subscribe' and
        request.args['hub.verify_token'] == VERIFY_TOKEN):
        # Validating webhook
        return request.args['hub.challenge']

    abort(403)


if __name__ == '__main__':
    app.run()
