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
def webhook(methods=['GET', 'POST']):
    if (request.args['hub.mode'] == 'subscribe' and
        request.args['hub.verify_token'] == VERIFY_TOKEN):
        print('Validating webhook')
        return request.args['hub.challenge']

    print('Validation failed')
    abort(403)

if __name__ == '__main__':
    app.run()
